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

echo 'Authorizing Azure Blob Storage connection...'
currentStatus=$(az connector-namespace connection show \
  -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
  -n "$connectorNamespaceConnectionName" --query 'properties.overallStatus' -o tsv)
currentStatus="${currentStatus%$'\r'}"

if [[ "$(printf '%s' "$currentStatus" | tr '[:upper:]' '[:lower:]')" == 'connected' ]]; then
  echo 'Connection is already authorized.'
else
  echo 'Sign in with the same user granted source storage access during provisioning.'
  consentLink=""
  for attempt in 1 2 3 4 5; do
    consentLink=$(az connector-namespace connection list-consent-links \
      -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
      --connection-name "$connectorNamespaceConnectionName" \
      --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
      --query 'value[0].link' -o tsv 2>/dev/null) || consentLink=""
    consentLink="${consentLink%$'\r'}"
    if [[ -z "$consentLink" || "$consentLink" == 'null' ]]; then
      consentLink=$(az connector-namespace connection list-consent-links \
        -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
        --connection-name "$connectorNamespaceConnectionName" \
        --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
        --query 'link' -o tsv 2>/dev/null) || consentLink=""
    fi
    consentLink="${consentLink%$'\r'}"
    if [[ -n "$consentLink" && "$consentLink" != 'null' ]]; then
      break
    fi
    if [[ "$attempt" != '5' ]]; then
      echo "Consent link attempt $attempt failed. Retrying in 5 seconds..."
      sleep 5
    fi
  done
  if [[ -z "$consentLink" || "$consentLink" == 'null' ]]; then
    echo 'ERROR: Failed to create consent link.' >&2
    exit 1
  fi
  echo "Consent URL: $consentLink"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$consentLink" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$consentLink" >/dev/null 2>&1 || true
  else
    echo 'Open the consent URL manually.'
  fi
  deadline=$((SECONDS + 300))
  while (( SECONDS < deadline )); do
    sleep 3
    currentStatus=$(az connector-namespace connection show \
      -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
      -n "$connectorNamespaceConnectionName" --query 'properties.overallStatus' -o tsv)
    currentStatus="${currentStatus%$'\r'}"
    echo "Connection status: $currentStatus"
    if [[ "$(printf '%s' "$currentStatus" | tr '[:upper:]' '[:lower:]')" == 'connected' ]]; then
      break
    fi
  done
  if [[ "$(printf '%s' "$currentStatus" | tr '[:upper:]' '[:lower:]')" != 'connected' ]]; then
    echo 'ERROR: Timed out waiting for the connection to reach Connected status.' >&2
    exit 1
  fi
fi

echo 'Done. The Azure Blob connection is authorized; Bicep manages the Poll trigger.'