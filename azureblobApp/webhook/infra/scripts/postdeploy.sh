#!/bin/bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_dir="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/local-settings.sh"
jq() { connector_jq "$@"; }
force=false
for argument in "$@"; do
  case "$argument" in --force-local-settings) force=true ;; *) echo 'Unknown argument.' >&2; exit 1 ;; esac
done
temp_dir=""
cleanup_files() {
  result=$?
  trap - EXIT
  if [[ -n "$temp_dir" ]]; then
    rm -f -- "$temp_dir/notification.json" "$temp_dir/parameters.json" || result=1
    rmdir -- "$temp_dir" || result=1
  fi
  exit "$result"
}
trap cleanup_files EXIT

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
           .functionAppName, .functionAppDefaultHostname, .AZURE_SUBSCRIPTION_ID, .monitoredStorageAccountName,
           .monitoredContainerName; required_string)
    then . else error("Required deployment outputs must be nonempty strings.") end
')
resourceGroupName=$(printf '%s' "$outputs" | jq -r '.resourceGroupName')
connectorNamespaceName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceName')
connectorNamespaceConnectionName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceConnectionName')
functionAppName=$(printf '%s' "$outputs" | jq -r '.functionAppName')
functionAppDefaultHostname=$(printf '%s' "$outputs" | jq -r '.functionAppDefaultHostname')
subscriptionId=$(printf '%s' "$outputs" | jq -r '.AZURE_SUBSCRIPTION_ID')
monitoredStorageAccountName=$(printf '%s' "$outputs" | jq -r '.monitoredStorageAccountName')
containerName=$(printf '%s' "$outputs" | jq -r '.monitoredContainerName')

settings=$(jq -n '{IsEncrypted:false,Values:{AzureWebJobsStorage:"UseDevelopmentStorage=true",
  FUNCTIONS_WORKER_RUNTIME:"python",PYTHON_ISOLATE_WORKER_DEPENDENCIES:"1"}}')
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

folderId=$(printf '%%2f%s' "$containerName" | base64 | tr -d '\r\n')
existingTriggers=$(az connector-namespace trigger list -g "$resourceGroupName" --namespace "$connectorNamespaceName" --query '[].name' -o json 2>/dev/null)
jq -e 'type == "array" and all(.[]; type == "string" and test("\\S"))' <<< "$existingTriggers" >/dev/null
connectorExtensionKey=$(az functionapp keys list -g "$resourceGroupName" -n "$functionAppName" --query 'systemKeys.connector_extension' -o tsv 2>/dev/null)
connectorExtensionKey="${connectorExtensionKey%$'\r'}"
if [[ -z "$connectorExtensionKey" || "$connectorExtensionKey" == 'null' ]]; then
  echo 'ERROR: Failed to fetch the connector_extension system key.' >&2
  exit 1
fi

functionName='OnAzureBlobUpdatedFile'
operationName='OnUpdatedFiles_V2'
triggerName="${connectorNamespaceConnectionName}-$(printf '%s' "$functionName" | tr '[:upper:]' '[:lower:]')"
callbackUrl="https://${functionAppDefaultHostname}/runtime/webhooks/connector?functionName=${functionName}"
temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/blob-callback.XXXXXXXX")
notifFile="$temp_dir/notification.json"
parametersFile="$temp_dir/parameters.json"
jq -n --arg url "$callbackUrl" --arg key "$connectorExtensionKey" \
  '{callbackUrl: $url, authentication: {type: "QueryString", name: "code", value: $key}}' > "$notifFile"

jq -n --arg dataset "$monitoredStorageAccountName" --arg folder "$folderId" \
  '[{name:"dataset",value:$dataset},{name:"folderId",value:$folder}]' > "$parametersFile"
connectionDetails=$(jq -cn --arg connection "$connectorNamespaceConnectionName" '{connectionName:$connection,connectorName:"azureblob"}')
metadata=$(jq -cn --arg app "$functionAppName" --arg group "$resourceGroupName" \
  --arg subscription "$subscriptionId" --arg functionName "$functionName" \
  '{destinationType:"functionApp",functionAppName:$app,functionAppResourceGroup:$group,
    functionAppSubscriptionId:$subscription,functionName:$functionName,recurrenceFrequency:"Minute",recurrenceInterval:"5"}')
verb=create
if jq -e --arg name "$triggerName" 'index($name) != null' <<< "$existingTriggers" >/dev/null; then verb=update; fi
az connector-namespace trigger "$verb" \
  -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
  -n "$triggerName" \
  --connection-details "$connectionDetails" \
  --operation-name "$operationName" \
  --parameters "@$parametersFile" \
  --notification-details "@${notifFile}" \
  --description 'When a blob is added or modified (properties only) (V2)' \
  --state Enabled --metadata "$metadata" -o none 2>/dev/null

echo "Done. Upload blobs to '$containerName' in '$monitoredStorageAccountName' to fire the trigger."