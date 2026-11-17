#!/usr/bin/env bash
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
az extension show --name connector-namespace --query name -o tsv >/dev/null
command -v jq >/dev/null || { echo 'jq is required.' >&2; exit 1; }

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
  | if all(.triggerConfigSettings | .OnOneDriveNewFileTriggerConfigName,
        .OnOneDriveUpdatedFileTriggerConfigName,
        .OnOneDriveNewFileContentTriggerConfigName,
        .OnOneDriveUpdatedFileContentTriggerConfigName; required_string)
      then . else error("All four trigger config names must be nonempty strings.") end
')
resourceGroupName=$(printf '%s' "$outputs" | jq -r '.resourceGroupName')
connectorNamespaceName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceName')
connectorNamespaceConnectionName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceConnectionName')

settings=$(printf '%s' "$outputs" | jq '{
    IsEncrypted: false,
    Values: ({
      AzureWebJobsStorage: "UseDevelopmentStorage=true",
      FUNCTIONS_WORKER_RUNTIME: "python",
      PYTHON_ISOLATE_WORKER_DEPENDENCIES: "1",
      ConnectorNamespace__pollingEndpoint: .connectorPollingEndpoint
    } + (.triggerConfigSettings | {
      OnOneDriveNewFileTriggerConfigName,
      OnOneDriveUpdatedFileTriggerConfigName,
      OnOneDriveNewFileContentTriggerConfigName,
      OnOneDriveUpdatedFileContentTriggerConfigName
    }))
  }')
write_local_settings "$settings" "$force"

echo 'Done. local.settings.json is ready for local runs; the enabled Poll triggers were created by the triggers layer.'
