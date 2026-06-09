#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_notif_files=()
cleanup_notif_files() { for f in "${_notif_files[@]}"; do rm -f "$f"; done; }
trap cleanup_notif_files EXIT

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Post-deployment configuration...${NC}"

outputs=$(azd env get-values --output json)

if ! command -v jq &> /dev/null; then
  echo -e "${RED}Error: jq is required for this script. Please install jq.${NC}"
  exit 1
fi

if ! az extension show --name connector-namespace --query name -o tsv >/dev/null 2>/dev/null; then
  echo -e "${RED}ERROR: The 'connector-namespace' Azure CLI extension is required.${NC}"
  echo -e "${RED}Install: curl -fsSL https://aka.ms/connector-namespace-cli-install | sh${NC}"
  exit 1
fi

resourceGroupName=$(echo "$outputs" | jq -r '.resourceGroupName')
connectorNamespaceName=$(echo "$outputs" | jq -r '.connectorNamespaceName')
connectorNamespaceConnectionName=$(echo "$outputs" | jq -r '.connectorNamespaceConnectionName')
functionAppName=$(echo "$outputs" | jq -r '.functionAppName')

# --- Required Teams identifiers ---
teamsGroupId=$(echo "$outputs" | jq -r '.TEAMS_GROUP_ID // empty')
teamsChannelId=$(echo "$outputs" | jq -r '.TEAMS_CHANNEL_ID // empty')

invoke_graph() {
  az rest --method get --url "$1" --resource https://graph.microsoft.com 2>/dev/null
}

get_connection_status() {
  az connector-namespace connection show \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$connectorNamespaceConnectionName" \
    --query "properties.overallStatus" -o tsv 2>/dev/null || true
}

select_from_list() {
  local title="$1"
  local json_array="$2"
  local label_prop="$3"

  echo -e "\n${CYAN}${title}${NC}"
  local count
  count=$(echo "$json_array" | jq 'length')
  for ((i=0; i<count; i++)); do
    local label
    label=$(echo "$json_array" | jq -r ".[$i].$label_prop")
    echo "  [$((i+1))] $label"
  done
  while true; do
    read -rp "Enter number (1-$count): " num
    if [[ "$num" =~ ^[0-9]+$ ]] && [ "$num" -ge 1 ] && [ "$num" -le "$count" ]; then
      echo "$json_array" | jq -r ".[$((num-1))]"
      return
    fi
    echo -e "${YELLOW}Invalid selection.${NC}"
  done
}

if [ -z "$teamsGroupId" ] || [ -z "$teamsChannelId" ]; then
  echo -e "\n${YELLOW}TEAMS_GROUP_ID / TEAMS_CHANNEL_ID not set. Fetching your Teams from Microsoft Graph...${NC}"

  teamsJson=$(invoke_graph 'https://graph.microsoft.com/v1.0/me/joinedTeams?$select=id,displayName')
  teamsArray=$(echo "$teamsJson" | jq '.value')
  teamsCount=$(echo "$teamsArray" | jq 'length')

  if [ -z "$teamsArray" ] || [ "$teamsCount" -eq 0 ]; then
    echo -e "${RED}ERROR: Could not list your joined teams via Microsoft Graph.${NC}"
    echo -e "${RED}       Set the values manually:${NC}"
    echo -e "${RED}         azd env set TEAMS_GROUP_ID   <team / M365 group object id>${NC}"
    echo -e "${RED}         azd env set TEAMS_CHANNEL_ID <channel id>${NC}"
    exit 1
  fi

  if [ -z "$teamsGroupId" ]; then
    selected=$(select_from_list "Select a team:" "$teamsArray" "displayName")
    teamsGroupId=$(echo "$selected" | jq -r '.id')
    azd env set TEAMS_GROUP_ID "$teamsGroupId" >/dev/null
    echo -e "${GREEN}Saved TEAMS_GROUP_ID=$teamsGroupId${NC}"
  fi

  if [ -z "$teamsChannelId" ]; then
    channelsJson=$(invoke_graph "https://graph.microsoft.com/v1.0/teams/$teamsGroupId/channels?\$select=id,displayName")
    channelsArray=$(echo "$channelsJson" | jq '.value')
    channelsCount=$(echo "$channelsArray" | jq 'length')
    if [ -z "$channelsArray" ] || [ "$channelsCount" -eq 0 ]; then
      echo -e "${RED}ERROR: Could not list channels for team $teamsGroupId.${NC}"
      exit 1
    fi
    selected=$(select_from_list "Select a channel:" "$channelsArray" "displayName")
    teamsChannelId=$(echo "$selected" | jq -r '.id')
    azd env set TEAMS_CHANNEL_ID "$teamsChannelId" >/dev/null
    echo -e "${GREEN}Saved TEAMS_CHANNEL_ID=$teamsChannelId${NC}"
  fi
fi

# Fetch the connector extension system key
echo -e "${CYAN}Fetching connector extension key for ${functionAppName}...${NC}"
connectorExtensionKey=$(az functionapp keys list -g "${resourceGroupName}" -n "${functionAppName}" --query "systemKeys.connector_extension" -o tsv)

create_trigger_config() {
  local functionName="$1"
  local operationName="$2"
  local description="$3"
  local parametersShorthand="$4"
  local triggerName="${connectorNamespaceConnectionName}-$(echo "${functionName}" | tr '[:upper:]' '[:lower:]')"
  local callbackUrl="https://${functionAppName}.azurewebsites.net/runtime/webhooks/connector?functionName=${functionName}&code=${connectorExtensionKey}"
  local notifFile="${SCRIPT_DIR}/.notification-details.${RANDOM}.${RANDOM}.json"
  _notif_files+=("$notifFile")
  printf '{"callbackUrl":"%s"}' "$callbackUrl" > "$notifFile"

  echo -e "${CYAN}  Creating trigger: ${functionName} -> ${operationName}${NC}"

  az connector-namespace trigger delete \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$triggerName" --yes 2>/dev/null || true

  az connector-namespace trigger create \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$triggerName" \
    --connection-details "{connectionName:${connectorNamespaceConnectionName},connectorName:teams}" \
    --operation-name "$operationName" \
    --parameters "$parametersShorthand" \
    --notification-details "@${notifFile}" \
    --description "$description" \
    --metadata "{destinationType:functionApp,functionAppName:${functionAppName},functionAppResourceGroup:${resourceGroupName},functionAppSubscriptionId:${AZURE_SUBSCRIPTION_ID},functionName:${functionName},recurrenceFrequency:Minute,recurrenceInterval:'5'}" \
    -o none

  rm -f "$notifFile"
}

# --- Create trigger configs for all 4 functions ---
echo -e "${YELLOW}Creating Connector Namespace trigger configs...${NC}"

create_trigger_config "OnNewChannelMessage" "OnNewChannelMessage" \
  "When a new channel message is added" \
  "[{name:groupId,value:'${teamsGroupId}'},{name:channelId,value:'${teamsChannelId}'}]"

create_trigger_config "OnNewChannelMessageMentioningMe" "OnNewChannelMessageMentioningMe" \
  "When I am mentioned in a channel message" \
  "[{name:groupId,value:'${teamsGroupId}'},{name:channelId,value:'${teamsChannelId}'}]"

create_trigger_config "OnGroupMembershipAdd" "OnGroupMembershipAdd" \
  "When a new team member is added" \
  "[{name:groupId,value:'${teamsGroupId}'}]"

create_trigger_config "OnGroupMembershipRemoval" "OnGroupMembershipRemoval" \
  "When a team member is removed" \
  "[{name:groupId,value:'${teamsGroupId}'}]"

echo -e "${GREEN}✅ All trigger configs created.${NC}"

echo ""
echo -e "${YELLOW}Authorizing teams connection...${NC}"

currentStatus=$(get_connection_status)
if [ "$currentStatus" = "Connected" ]; then
  echo -e "${GREEN}Teams connection already Connected. Skipping consent.${NC}"
else
  echo -e "${CYAN}-> A browser tab will open. Sign in with the Teams account you want to monitor.${NC}"

  consentUrl=""
  for attempt in 1 2 3 4 5; do
    consentUrl=$(az connector-namespace connection list-consent-links \
      -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
      --connection-name "$connectorNamespaceConnectionName" \
      --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
      --query "value[0].link" -o tsv 2>/dev/null || true)

    if [ -n "$consentUrl" ]; then
      break
    fi

    if [ "$attempt" -lt 5 ]; then
      echo -e "${YELLOW}Consent link not ready yet. Retrying in 5 seconds...${NC}"
      sleep 5
    fi
  done

  if [ -z "$consentUrl" ]; then
    echo -e "${RED}Failed to generate a consent URL for the Teams connection.${NC}"
    exit 1
  fi

  echo -e "${CYAN}Consent URL: ${consentUrl}${NC}"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$consentUrl" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$consentUrl" >/dev/null 2>&1 || true
  else
    echo -e "${YELLOW}No browser opener detected. Paste the consent URL into a browser manually.${NC}"
  fi
  echo -e "${YELLOW}If the browser did not open, paste this URL into a browser:${NC}"
  echo "$consentUrl"

  lastReportedStatus="$currentStatus"
  if [ -n "$lastReportedStatus" ]; then
    echo -e "${CYAN}Connection status: ${lastReportedStatus}${NC}"
  fi

  deadline=$((SECONDS + 300))
  pollStatus="$currentStatus"
  while [ $SECONDS -lt $deadline ]; do
    pollStatus=$(get_connection_status)

    if [ -n "$pollStatus" ] && [ "$pollStatus" != "$lastReportedStatus" ]; then
      echo -e "${CYAN}Connection status: ${pollStatus}${NC}"
      lastReportedStatus="$pollStatus"
    fi

    if [ "$pollStatus" = "Connected" ]; then
      echo -e "${GREEN}Teams connection authorized.${NC}"
      break
    fi

    sleep 3
  done

  if [ "$pollStatus" != "Connected" ]; then
    echo -e "${RED}Timed out waiting for the Teams connection to reach Connected status.${NC}"
    exit 1
  fi
fi

echo ""
echo -e "${GREEN}✅ Done. All 4 Teams triggers are configured.${NC}"
echo -e "${GREEN}   Tail logs:  az functionapp log tail -g ${resourceGroupName} -n ${functionAppName}${NC}"
echo ""