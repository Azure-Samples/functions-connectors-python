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

if ! az extension show --name connector-namespace --query name -o tsv 2>/dev/null; then
  echo -e "${RED}ERROR: The 'connector-namespace' Azure CLI extension is required.${NC}"
  echo -e "${RED}Install: curl -fsSL https://aka.ms/connector-namespace-cli-install | sh${NC}"
  exit 1
fi

outputs=$(azd env get-values --output json)

if ! command -v jq &> /dev/null; then
  echo -e "${RED}Error: jq is required for this script. Please install jq.${NC}"
  exit 1
fi

resourceGroupName=$(echo "$outputs" | jq -r '.resourceGroupName')
connectorNamespaceName=$(echo "$outputs" | jq -r '.connectorNamespaceName')
connectorNamespaceConnectionName=$(echo "$outputs" | jq -r '.connectorNamespaceConnectionName')
functionAppName=$(echo "$outputs" | jq -r '.functionAppName')

# Fetch the connector extension system key
echo -e "${CYAN}Fetching connector extension key for ${functionAppName}...${NC}"
connectorExtensionKey=$(az functionapp keys list -g "${resourceGroupName}" -n "${functionAppName}" --query "systemKeys.connector_extension" -o tsv)

# --- Helper: create a trigger config on the Connector Namespace ---
create_trigger_config() {
  local functionName="$1"
  local operationName="$2"
  local description="$3"
  local parametersShorthand="$4"

  local triggerName="${connectorNamespaceConnectionName}-$(echo "${functionName}" | tr '[:upper:]' '[:lower:]')"
  local callbackUrl="https://${functionAppName}.azurewebsites.net/runtime/webhooks/connector?functionName=${functionName}"
  local notifFile="${SCRIPT_DIR}/.notification-details.${RANDOM}.${RANDOM}.json"
  _notif_files+=("$notifFile")
  printf '{"callbackUrl":"%s","authentication":{"type":"QueryString","name":"code","value":"%s"}}' "$callbackUrl" "$connectorExtensionKey" > "$notifFile"

  echo -e "${CYAN}  Creating trigger: ${functionName} -> ${operationName}${NC}"

  az connector-namespace trigger delete \
    -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
    -n "${triggerName}" --yes 2>/dev/null || true

  az connector-namespace trigger create \
    -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
    -n "${triggerName}" \
    --connection-details "{connectionName:${connectorNamespaceConnectionName},connectorName:office365}" \
    --operation-name "${operationName}" \
    --parameters "${parametersShorthand}" \
    --notification-details "@${notifFile}" \
    --description "${description}" \
    --metadata "{destinationType:functionApp,functionAppName:${functionAppName},functionAppResourceGroup:${resourceGroupName},functionAppSubscriptionId:${AZURE_SUBSCRIPTION_ID},functionName:${functionName},recurrenceFrequency:Minute,recurrenceInterval:'5'}" \
    -o none

  rm -f "$notifFile"
}

# --- Create trigger configs for all 5 functions ---
echo -e "${YELLOW}Creating Connector Namespace trigger configs...${NC}"

create_trigger_config "OnNewEmail" "OnNewEmailV3" \
  "When a new email arrives" \
  "[{name:folderPath,value:'Inbox'},{name:importance,value:'High'}]"

create_trigger_config "OnFlaggedEmail" "OnFlaggedEmailV4" \
  "When an email is flagged" \
  "[{name:folderPath,value:'Inbox'}]"

create_trigger_config "OnNewMentionMeEmail" "OnNewMentionMeEmailV3" \
  "When a new email mentioning me arrives" \
  "[{name:folderPath,value:'Inbox'}]"

create_trigger_config "OnNewCalendarEvent" "CalendarGetOnNewItemsV3" \
  "When a new calendar event is created" \
  "[{name:table,value:'Calendar'}]"

create_trigger_config "OnUpcomingEvent" "OnUpcomingEventsV3" \
  "When an upcoming event is starting soon" \
  "[{name:table,value:'Calendar'}]"

echo -e "${GREEN}All trigger configs created.${NC}"

echo ""
echo -e "${YELLOW}Authorizing office365 connection...${NC}"

currentStatus=$(az connector-namespace connection show \
  -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
  -n "${connectorNamespaceConnectionName}" \
  --query "properties.overallStatus" -o tsv 2>/dev/null || true)
currentStatus=${currentStatus:-Unknown}

if [[ "${currentStatus}" == "Connected" ]]; then
  echo -e "${GREEN}Connection is already authorized.${NC}"
else
  echo -e "${CYAN}-> A browser tab will open. Sign in with the mailbox account whose Inbox you want to monitor.${NC}"

  consentLink=""
  for attempt in 1 2 3 4 5; do
    consentLink=$(az connector-namespace connection list-consent-links \
      -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
      --connection-name "${connectorNamespaceConnectionName}" \
      --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
      --query "value[0].link" -o tsv 2>/dev/null || true)

    if [[ -z "${consentLink}" || "${consentLink}" == "null" ]]; then
      consentLink=$(az connector-namespace connection list-consent-links \
        -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
        --connection-name "${connectorNamespaceConnectionName}" \
        --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" \
        --query "link" -o tsv 2>/dev/null || true)
    fi

    if [[ -n "${consentLink}" && "${consentLink}" != "null" ]]; then
      break
    fi

    if [[ "${attempt}" != "5" ]]; then
      echo -e "${YELLOW}listConsentLinks attempt ${attempt} failed. Retrying in 5 seconds...${NC}"
      sleep 5
    fi
  done

  if [[ -z "${consentLink}" || "${consentLink}" == "null" ]]; then
    echo -e "${RED}Failed to create consent link.${NC}"
    exit 1
  fi

  echo -e "${CYAN}Consent URL: ${consentLink}${NC}"

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${consentLink}" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "${consentLink}" >/dev/null 2>&1 || true
  else
    echo -e "${YELLOW}Unable to open a browser automatically. Paste the consent URL into your browser.${NC}"
  fi

  deadline=$((SECONDS + 300))
  lastPrintedStatus="${currentStatus}"
  echo -e "${CYAN}Connection status: ${currentStatus}${NC}"

  while (( SECONDS < deadline )); do
    sleep 3
    currentStatus=$(az connector-namespace connection show \
      -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
      -n "${connectorNamespaceConnectionName}" \
      --query "properties.overallStatus" -o tsv 2>/dev/null || true)
    currentStatus=${currentStatus:-Unknown}

    if [[ "${currentStatus}" != "${lastPrintedStatus}" ]]; then
      echo -e "${CYAN}Connection status: ${currentStatus}${NC}"
      lastPrintedStatus="${currentStatus}"
    fi

    if [[ "${currentStatus}" == "Connected" ]]; then
      break
    fi
  done

  if [[ "${currentStatus}" != "Connected" ]]; then
    echo -e "${RED}Timed out waiting for the connection to reach Connected status.${NC}"
    exit 1
  fi
fi

echo ""
echo -e "${GREEN}Done. All 5 Office 365 triggers are configured.${NC}"
echo -e "${GREEN}   Tail logs:  az functionapp log tail -g ${resourceGroupName} -n ${functionAppName}${NC}"
echo ""
