#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/local-settings.sh"
jq() { connector_jq "$@"; }
force=false
for argument in "$@"; do
  case "$argument" in --force-local-settings) force=true ;; *) echo 'Unknown argument.' >&2; exit 1 ;; esac
done

echo 'Post-deployment configuration...'
if ! az extension show --name connector-namespace --query name -o tsv 2>/dev/null; then
  echo "ERROR: The 'connector-namespace' Azure CLI extension is required." >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo 'ERROR: jq is required.' >&2
  exit 1
fi

outputs=$(azd env get-values --output json)
outputs=$(printf '%s' "$outputs" | jq -ce '
  def required_string: type == "string" and test("\\S") and . != "null";
  if type != "object" then error("Deployment outputs must be a JSON object.") else . end
  | if all(.resourceGroupName, .connectorNamespaceName, .connectorNamespaceConnectionName,
           .connectorPollingEndpoint; required_string)
    then . else error("Required deployment outputs must be nonempty strings.") end
  | .triggerConfigSettings |= (if type == "string" then fromjson else . end)
  | if (.triggerConfigSettings | type) != "object"
    then error("triggerConfigSettings must be a JSON object or a JSON-encoded object.") else . end
  | if (.triggerConfigSettings.OnAzureBlobUpdatedFileTriggerConfigName | required_string)
    then . else error("OnAzureBlobUpdatedFileTriggerConfigName must be a nonempty string.") end
')
resourceGroupName=$(printf '%s' "$outputs" | jq -r '.resourceGroupName')
connectorNamespaceName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceName')
connectorNamespaceConnectionName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceConnectionName')

settings=$(printf '%s' "$outputs" | jq '{
    IsEncrypted: false,
    Values: {
      AzureWebJobsStorage: "UseDevelopmentStorage=true",
      FUNCTIONS_WORKER_RUNTIME: "python",
      PYTHON_ISOLATE_WORKER_DEPENDENCIES: "1",
      ConnectorNamespace__pollingEndpoint: .connectorPollingEndpoint,
      OnAzureBlobUpdatedFileTriggerConfigName: .triggerConfigSettings.OnAzureBlobUpdatedFileTriggerConfigName
    }
  }')
write_local_settings "$settings" "$force"

echo 'Waiting for the managed-identity Azure Blob connection...'
for ((attempt=1; attempt<=100; attempt++)); do
  if ! currentStatus=$(az connector-namespace connection show \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$connectorNamespaceConnectionName" --query 'properties.overallStatus' -o tsv 2>/dev/null); then
    echo 'ERROR: Failed to read connection status.' >&2
    exit 1
  fi
  currentStatus=$(printf '%s' "$currentStatus" | tr '[:upper:]' '[:lower:]' | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  case "$currentStatus" in
    connected|ready) break ;;
    error)
      echo 'ERROR: The managed-identity Blob connection is in Error status. Check namespace source-storage RBAC.' >&2
      exit 1 ;;
  esac
  if (( attempt == 100 )); then
    echo 'ERROR: Timed out waiting for the managed-identity Blob connection to reach Connected or Ready status.' >&2
    exit 1
  fi
  sleep 3
done

echo 'Done. The managed-identity Azure Blob connection is ready; Bicep manages the Poll trigger.'