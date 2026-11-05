#!/usr/bin/env bash
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
notificationFile=""
parametersFile=""
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
az extension show --name connector-namespace --query name -o tsv >/dev/null
command -v jq >/dev/null || { echo 'jq is required.' >&2; exit 1; }
outputs=$(azd env get-values --output json)
outputs=$(printf '%s' "$outputs" | jq -ce '
  def required_string: type == "string" and test("\\S") and . != "null";
  if type != "object" then error("Deployment outputs must be a JSON object.") else . end
  | if all(.resourceGroupName, .connectorNamespaceName, .connectorNamespaceConnectionName,
           .functionAppName, .functionAppDefaultHostname, .AZURE_SUBSCRIPTION_ID; required_string)
    then . else error("Required deployment outputs must be nonempty strings.") end
  | if .ONEDRIVE_FOLDER_ID == null or (.ONEDRIVE_FOLDER_ID | type) == "string"
    then . else error("ONEDRIVE_FOLDER_ID must be a string.") end
')
resourceGroupName=$(printf '%s' "$outputs" | jq -r '.resourceGroupName')
connectorNamespaceName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceName')
onedriveConnectionName=$(printf '%s' "$outputs" | jq -r '.connectorNamespaceConnectionName')
functionAppName=$(printf '%s' "$outputs" | jq -r '.functionAppName')
functionAppDefaultHostname=$(printf '%s' "$outputs" | jq -r '.functionAppDefaultHostname')
subscriptionId=$(printf '%s' "$outputs" | jq -r '.AZURE_SUBSCRIPTION_ID')
onedriveFolderId="${ONEDRIVE_FOLDER_ID:-$(printf '%s' "$outputs" | jq -r '.ONEDRIVE_FOLDER_ID // empty')}"

settings=$(jq -n '{IsEncrypted: false, Values: {
    FUNCTIONS_WORKER_RUNTIME: "python",
    AzureWebJobsStorage: "UseDevelopmentStorage=true",
    PYTHON_ISOLATE_WORKER_DEPENDENCIES: "1"
  }}')
write_local_settings "$settings" "$force"

get_connection_status() {
  local status
  status=$(az connector-namespace connection show \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$onedriveConnectionName" --query 'properties.overallStatus' -o tsv) || return 1
  printf '%s\n' "${status%$'\r'}"
}

echo 'Authorizing OneDrive for Business connection...'
currentStatus=$(get_connection_status)
if [[ "$currentStatus" != 'Connected' ]]; then
  consentLink=""
  for attempt in 1 2 3 4 5; do
    consentLink=$(az connector-namespace connection list-consent-links \
      -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
      --connection-name "$onedriveConnectionName" \
      --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
      --query 'value[0].link' -o tsv 2>/dev/null) || consentLink=""
    consentLink="${consentLink%$'\r'}"
    if [[ -z "$consentLink" || "$consentLink" == 'null' ]]; then
      consentLink=$(az connector-namespace connection list-consent-links \
        -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
        --connection-name "$onedriveConnectionName" \
        --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
        --query 'link' -o tsv 2>/dev/null) || consentLink=""
    fi
    consentLink="${consentLink%$'\r'}"
    if [[ -n "$consentLink" && "$consentLink" != 'null' ]]; then break; fi
    if [[ "$attempt" != '5' ]]; then sleep 5; fi
  done
  if [[ -z "$consentLink" || "$consentLink" == 'null' ]]; then
    echo 'Failed to create consent link.' >&2
    exit 1
  fi
  echo "Sign in with the account that owns the OneDrive folder: $consentLink"
  if command -v xdg-open >/dev/null; then
    xdg-open "$consentLink" >/dev/null 2>&1 || true
  elif command -v open >/dev/null; then
    open "$consentLink" >/dev/null 2>&1 || true
  fi
  deadline=$((SECONDS + 300))
  while (( SECONDS < deadline )); do
    sleep 3
    currentStatus=$(get_connection_status)
    if [[ "$currentStatus" == 'Connected' ]]; then break; fi
  done
  if [[ "$currentStatus" != 'Connected' ]]; then
    echo 'Timed out waiting for the OneDrive connection to reach Connected status.' >&2
    exit 1
  fi
fi

select_onedrive_folder() {
  local folderIds=('root') folderPaths=('/')
  local depth=0 listingPath listing folders folderCount choice manual encodedId
  while true; do
    echo "Current folder: ${folderPaths[$depth]} [id: ${folderIds[$depth]}]" >&2
    if [[ "${folderIds[$depth]}" == 'root' ]]; then
      listingPath='/datasets/default/folders'
    else
      encodedId=$(jq -rn --arg identifier "${folderIds[$depth]}" '$identifier | @uri')
      listingPath="/datasets/default/folders/$encodedId"
    fi
    # Check failures explicitly because this function runs in a command substitution.
    listing=$(az connector-namespace connection invoke \
      -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
      --connection-name "$onedriveConnectionName" \
      --request "$(jq -cn --arg path "$listingPath" '{method:"get",path:$path}')" -o json) || return 1
    folders=$(printf '%s' "$listing" | jq -ce '
      .response
      | (.statusCode | tostring) as $status
      | if (($status | test("^2[0-9][0-9]$")) or
            (["OK", "Created", "Accepted", "NoContent"] | index($status)) != null)
        then .body else error("OneDrive folder listing failed.") end
      | if type == "string" then fromjson else . end
      | if type == "object" and has("value") then .value else . end
      | if type != "array" then error("OneDrive folder listing must contain an array.") else . end
      | map(select(.IsFolder == true))
      | if all(.[]; (.Id | type == "string" and test("\\S")))
        then . else error("OneDrive returned a folder without a connector identifier.") end
    ') || return 1
    folderCount=$(printf '%s' "$folders" | jq 'length') || return 1
    echo '[0] Use this folder; [u] Go up; [m] Enter connector folder ID; [q] Cancel' >&2
    printf '%s' "$folders" | jq -r 'to_entries[] | "[\(.key + 1)] \(.value.Name)"' >&2 || return 1
    read -r -p 'Choose a folder: ' choice || { echo 'No folder selection available. Set ONEDRIVE_FOLDER_ID.' >&2; return 1; }
    case "$choice" in
      0) printf '%s' "${folderIds[$depth]}"; return ;;
      u)
        if (( depth == 0 )); then echo 'Already at root.' >&2; return 1; fi
        depth=$((depth - 1))
        ;;
      m)
        read -r -p 'OneDrive connector folder ID: ' manual || return 1
        if [[ ! "$manual" =~ [^[:space:]] || "$manual" == 'null' ]]; then
          echo 'A connector folder identifier is required.' >&2
          return 1
        fi
        printf '%s' "$manual"
        return
        ;;
      q) echo 'Folder selection canceled. No trigger configs were created.' >&2; return 1 ;;
      *)
        if [[ ! "$choice" =~ ^[1-9][0-9]{0,5}$ ]] || (( choice > folderCount )); then
          echo 'Invalid folder selection.' >&2
          return 1
        fi
        folderIds[$((depth + 1))]=$(printf '%s' "$folders" | jq -r --argjson index "$((choice - 1))" '.[$index].Id') || return 1
        folderPaths[$((depth + 1))]="${folderPaths[$depth]%/}/$(printf '%s' "$folders" | jq -r --argjson index "$((choice - 1))" '.[$index].Name')"
        depth=$((depth + 1))
        ;;
    esac
  done
}

if [[ -z "$onedriveFolderId" ]]; then
  onedriveFolderId=$(select_onedrive_folder)
fi
if [[ ! "$onedriveFolderId" =~ [^[:space:]] || "$onedriveFolderId" == 'null' ]]; then
  echo 'Set ONEDRIVE_FOLDER_ID to a connector folder identifier or root, not a display path.' >&2
  exit 1
fi
azd env set ONEDRIVE_FOLDER_ID "$onedriveFolderId" >/dev/null

existingTriggers=$(az connector-namespace trigger list -g "$resourceGroupName" --namespace "$connectorNamespaceName" --query '[].name' -o json 2>/dev/null)
jq -e 'type == "array" and all(.[]; type == "string" and test("\\S"))' <<< "$existingTriggers" >/dev/null
connectorExtensionKey=$(az functionapp keys list -g "$resourceGroupName" -n "$functionAppName" --query 'systemKeys.connector_extension' -o tsv 2>/dev/null)
connectorExtensionKey="${connectorExtensionKey%$'\r'}"
if [[ -z "$connectorExtensionKey" || "$connectorExtensionKey" == 'null' ]]; then
  echo 'Could not fetch the connector_extension system key.' >&2
  exit 1
fi

temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/onedrive-callback.XXXXXXXX")
create_trigger() {
  local functionName="$1" operationName="$2" triggerName callbackUrl metadata
  triggerName="${onedriveConnectionName}-$(printf '%s' "$functionName" | tr '[:upper:]' '[:lower:]')"
  callbackUrl="https://${functionAppDefaultHostname}/runtime/webhooks/connector?functionName=${functionName}"
  notificationFile="$temp_dir/notification.json"
  parametersFile="$temp_dir/parameters.json"
  jq -n --arg url "$callbackUrl" --arg key "$connectorExtensionKey" \
    '{callbackUrl: $url, authentication: {type: "QueryString", name: "code", value: $key}}' > "$notificationFile"
  jq -n --arg identifier "$onedriveFolderId" '[{name: "folderId", value: $identifier}]' > "$parametersFile"
  metadata=$(jq -cn --arg app "$functionAppName" --arg group "$resourceGroupName" \
    --arg subscription "$subscriptionId" --arg functionName "$functionName" \
    '{destinationType: "functionApp", functionAppName: $app, functionAppResourceGroup: $group,
      functionAppSubscriptionId: $subscription, functionName: $functionName,
      recurrenceFrequency: "Minute", recurrenceInterval: "5"}')
  local verb=create connectionDetails
  if jq -e --arg name "$triggerName" 'index($name) != null' <<< "$existingTriggers" >/dev/null; then verb=update; fi
  connectionDetails=$(jq -cn --arg connection "$onedriveConnectionName" '{connectionName:$connection,connectorName:"onedriveforbusiness"}')
  az connector-namespace trigger "$verb" \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" -n "$triggerName" \
    --connection-details "$connectionDetails" \
    --operation-name "$operationName" --parameters "@$parametersFile" \
    --notification-details "@$notificationFile" --description "OneDrive $operationName -> $functionName" \
    --state Enabled --metadata "$metadata" -o none 2>/dev/null
  rm -f -- "$notificationFile" "$parametersFile"
  notificationFile=""
  parametersFile=""
}

create_trigger 'OnOneDriveNewFile' 'OnNewFilesV2'
create_trigger 'OnOneDriveUpdatedFile' 'OnUpdatedFilesV2'
create_trigger 'OnOneDriveNewFileContent' 'OnNewFileV2'
create_trigger 'OnOneDriveUpdatedFileContent' 'OnUpdatedFileV2'
echo 'All four Connector Namespace trigger configs created successfully.'