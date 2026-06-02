#!/bin/bash
# Post-deployment configuration for the office365AppPython.
#
# Uses the official `connector-namespace` Azure CLI extension from
# https://github.com/Azure/Connectors. Two responsibilities:
#   1. Create one Connector Namespace trigger config per Functions trigger
#      in this app, each POSTing to the function's connector webhook URL.
#   2. Walk the operator through OAuth consent for the Office 365 Outlook
#      connection.

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Post-deployment configuration...${NC}"

if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is required for this script. Please install jq.${NC}"
    exit 1
fi

# --- Read azd outputs --------------------------------------------------------
outputs=$(azd env get-values --output json)

resourceGroupName=$(echo "$outputs" | jq -r '.resourceGroupName')
connectorNamespaceName=$(echo "$outputs" | jq -r '.connectorNamespaceName')
office365ConnectionName=$(echo "$outputs" | jq -r '.office365ConnectionName')
functionAppName=$(echo "$outputs" | jq -r '.functionAppName')

if [[ -z "$resourceGroupName" || -z "$connectorNamespaceName" || -z "$office365ConnectionName" || -z "$functionAppName" ]]; then
    echo -e "${RED}ERROR: required azd outputs missing. Run 'azd provision' first.${NC}"
    exit 1
fi

# --- Verify the connector-namespace az CLI extension is installed ----------
# This script does NOT auto-install the extension. Install it once with:
#   az extension add --source <connector_namespace-*.whl URL from
#                              https://github.com/Azure/Connectors/releases>
extInstalled="$(az extension show --name connector-namespace --query name -o tsv 2>/dev/null || true)"
if [[ -z "$extInstalled" ]]; then
    echo -e "${RED}ERROR: 'connector-namespace' Azure CLI extension is not installed.${NC}" >&2
    echo -e "${RED}       Download the latest 'connector_namespace-*.whl' from${NC}" >&2
    echo -e "${RED}       https://github.com/Azure/Connectors/releases and run:${NC}" >&2
    echo -e "${RED}         az extension add --source <wheel-url-or-path>${NC}" >&2
    echo -e "${RED}       Then re-run: azd hooks run postdeploy${NC}" >&2
    exit 2
fi

# --- Create Connector Namespace trigger configs -----------------------------
echo ""
echo -e "${CYAN}Fetching connector extension key for ${functionAppName}...${NC}"
connectorExtensionKey=$(az functionapp keys list -g "${resourceGroupName}" -n "${functionAppName}" --query "systemKeys.connector_extension" -o tsv)
if [[ -z "$connectorExtensionKey" ]]; then
    echo -e "${RED}ERROR: could not fetch connector_extension system key from ${functionAppName}.${NC}"
    exit 1
fi

connectionDetails=$(jq -nc --arg conn "${office365ConnectionName}" \
    '{connectorName:"office365", connectionName:$conn}')

# functionName | operationName | parameters JSON
triggers=(
    "OnNewEmail|OnNewEmailV3|[{\"name\":\"folderPath\",\"value\":\"Inbox\"}]"
    "OnFlaggedEmail|OnFlaggedEmailV3|[{\"name\":\"folderPath\",\"value\":\"Inbox\"}]"
    "OnNewMentionMeEmail|OnNewMentionMeEmailV3|[{\"name\":\"folderPath\",\"value\":\"Inbox\"}]"
    "OnNewCalendarEvent|CalendarGetOnNewItemsV3|[{\"name\":\"table\",\"value\":\"Calendar\"}]"
    "OnUpcomingEvent|OnUpcomingEventsV3|[{\"name\":\"table\",\"value\":\"Calendar\"},{\"name\":\"lookAheadTimeInMinutes\",\"value\":15}]"
)

for entry in "${triggers[@]}"; do
    IFS='|' read -r functionName operationName parameters <<< "$entry"

    triggerName="${office365ConnectionName}-$(echo "$functionName" | tr '[:upper:]' '[:lower:]')"
    callbackUrl="https://${functionAppName}.azurewebsites.net/runtime/webhooks/connector?functionName=${functionName}&code=${connectorExtensionKey}"
    notificationDetails=$(jq -nc --arg url "${callbackUrl}" '{callbackUrl:$url, httpMethod:"Post"}')

    echo ""
    echo -e "${YELLOW}Creating trigger '${triggerName}' for ${functionName} (${operationName})...${NC}"

    az connector-namespace trigger delete \
        -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
        -n "${triggerName}" --yes 2>/dev/null || true

    az connector-namespace trigger create \
        -g "${resourceGroupName}" \
        --namespace "${connectorNamespaceName}" \
        -n "${triggerName}" \
        --connection-details "${connectionDetails}" \
        --operation-name "${operationName}" \
        --parameters "${parameters}" \
        --notification-details "${notificationDetails}" \
        --state "Enabled" \
        --description "Office 365 ${operationName} -> ${functionName}"
done

echo ""
echo -e "${GREEN}✅ Connector Namespace trigger configs created successfully.${NC}"

# --- Authorize the Office 365 connection (OAuth consent) --------------------
echo ""
echo -e "${YELLOW}Authorizing Office 365 connection via Azure CLI...${NC}"

open_url() {
    local url="$1"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
        open "$url" >/dev/null 2>&1 || true
    elif command -v wslview >/dev/null 2>&1; then
        wslview "$url" >/dev/null 2>&1 || true
    fi
}

authorize_connection() {
    local connectionName="$1"
    local description="$2"

    echo -e "${CYAN}-> Authorizing ${description} connection: ${connectionName}${NC}"

    local currentStatus
    currentStatus=$(az connector-namespace connection show \
        -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
        -n "${connectionName}" --query "properties.overallStatus" -o tsv 2>/dev/null || echo "")
    if [[ "$(echo "$currentStatus" | tr '[:upper:]' '[:lower:]')" == "connected" ]]; then
        echo -e "${GREEN}   already Connected; skipping consent flow${NC}"
        return
    fi

    local params consentJson link
    params='[{"parameterName":"token","redirectUrl":"https://portal.azure.com"}]'
    consentJson=$(az connector-namespace connection list-consent-links \
        -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
        --connection-name "${connectionName}" --parameters "${params}" -o json 2>/dev/null || echo "")
    link=$(echo "${consentJson}" | jq -r '.value[0].link // empty' 2>/dev/null || echo "")
    if [[ -z "${link}" ]]; then
        echo -e "${RED}   list-consent-links returned no link; skipping${NC}"
        return
    fi

    echo -e "${CYAN}   opening browser for OAuth consent...${NC}"
    echo -e "${CYAN}   (if no tab opens, paste this URL manually:${NC}"
    echo -e "${CYAN}      ${link})${NC}"
    open_url "${link}"

    local deadline=$(($(date +%s) + 300))
    local lastStatus=""
    local s=""
    while [[ $(date +%s) -lt $deadline ]]; do
        s=$(az connector-namespace connection show \
            -g "${resourceGroupName}" --namespace "${connectorNamespaceName}" \
            -n "${connectionName}" --query "properties.overallStatus" -o tsv 2>/dev/null || echo "")
        if [[ "$s" != "$lastStatus" ]]; then
            echo -e "${CYAN}   status: ${s:-?}${NC}"
            lastStatus="$s"
        fi
        if [[ "$(echo "$s" | tr '[:upper:]' '[:lower:]')" == "connected" ]]; then
            echo -e "${GREEN}   ✓ ${connectionName} authenticated${NC}"
            return
        fi
        sleep 3
    done
    echo -e "${YELLOW}   timed out waiting for consent (5 min). Re-run azd up or this script when ready.${NC}"
}

authorize_connection "${office365ConnectionName}" "Office 365 Outlook"

echo ""
echo -e "${GREEN}✅ Post-deployment configuration complete.${NC}"
echo ""
