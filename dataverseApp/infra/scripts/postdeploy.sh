#!/usr/bin/env bash
# Post-deployment configuration for the dataverseApp (Python).
#
# The Microsoft Dataverse connection uses OAuth authentication. This script
# authorizes the connection via interactive consent (sign in with an account
# that has access to the target Dataverse environment), then creates the trigger
# config pointing at the function's connector webhook URL.
#
# Trigger: GetOnNewItems_V2 — fires when a new row is added to the table.
#   dataset = <Dataverse org URL>    (the DataSet name, e.g. https://org.crm.dynamics.com)
#   table   = <DATAVERSE_TABLE_NAME> (entity set / plural logical name, e.g. accounts)
#
# Notes:
#   - Do NOT pass $top: the poll fails with 400 when Change Tracking is enabled.
#   - The connected Dataverse identity needs Global Read on the table (these row
#     triggers are Admin Only); otherwise the poll returns 403 Forbidden.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_notif_files=()
cleanup_notif_files() { for f in "${_notif_files[@]}"; do rm -f "$f"; done; }
trap cleanup_notif_files EXIT

echo "Post-deployment configuration..."

# --- Pre-flight: verify the connector-namespace CLI extension is installed ----
if ! az extension show --name connector-namespace --query name -o tsv 2>/dev/null; then
    echo "ERROR: The 'connector-namespace' Azure CLI extension is required."
    echo "Install: curl -fsSL https://aka.ms/connector-namespace-cli-install | sh"
    exit 1
fi

# --- Read azd outputs --------------------------------------------------------
eval "$(azd env get-values)"

: "${resourceGroupName:?required azd output missing}"
: "${connectorNamespaceName:?required azd output missing}"
: "${connectorNamespaceConnectionName:?required azd output missing}"
: "${functionAppName:?required azd output missing}"

tableName="${dataverseTableName:-accounts}"
environmentUrl="${dataverseEnvironmentUrl:-}"
environmentName="${dataverseEnvironmentName:-}"

# --- Resolve the org URL from the environment friendly name (Global Discovery) ---
# If DATAVERSE_ENVIRONMENT_URL is not set but a friendly name is, look up the org
# URL via the Dataverse Global Discovery Service using the signed-in az identity.
if [ -z "$environmentUrl" ] && [ -n "$environmentName" ]; then
    echo "Resolving org URL for environment '${environmentName}' via Global Discovery..."
    token=$(az account get-access-token --resource https://globaldisco.crm.dynamics.com --query accessToken -o tsv 2>/dev/null || true)
    if [ -z "$token" ]; then
        echo "ERROR: could not obtain a Dataverse token. Ensure your 'az login' identity has access to the"
        echo "       environment, or set DATAVERSE_ENVIRONMENT_URL explicitly and re-provision."
        exit 1
    fi
    instances=$(curl -s -H "Authorization: Bearer $token" https://globaldisco.crm.dynamics.com/api/discovery/v2.0/Instances)
    environmentUrl=$(echo "$instances" | jq -r --arg n "$environmentName" \
        '.value[] | select((.FriendlyName|ascii_downcase) == ($n|ascii_downcase)) | .Url' | head -n1 | sed 's#/$##')
    if [ -z "$environmentUrl" ]; then
        echo "ERROR: no environment named '${environmentName}' is visible to your identity. Environments available to you:"
        echo "$instances" | jq -r '.value[] | "  - \(.FriendlyName)  ->  \(.Url)"'
        exit 1
    fi
    echo "   resolved: $environmentUrl"
fi

if [ -z "$environmentUrl" ]; then
    echo "ERROR: Dataverse environment is not set. Provide the friendly name (auto-resolved) or the URL:"
    echo "  azd env set DATAVERSE_ENVIRONMENT_NAME 'Contoso (default)'"
    echo "  # or"
    echo "  azd env set DATAVERSE_ENVIRONMENT_URL 'https://<your-org>.crm.dynamics.com'"
    echo "  azd provision"
    exit 1
fi

# GetOnNewItems_V2 uses the org URL as the "dataset" value (no trailing slash).
dataset="${environmentUrl%/}"

echo "Environment : ${environmentUrl}${environmentName:+ (${environmentName})}"
echo "Dataset     : $dataset"
echo "Table       : $tableName"

# Persist the resolved org URL as an app setting so the ListDataverseRows action
# (which reads DATAVERSE_ENVIRONMENT_URL directly) uses the org URL as its dataset,
# matching the trigger. Without this, a friendly-name-only config leaves the setting
# empty and the action would send the name, which the connector rejects (400).
echo "Persisting resolved org URL to $functionAppName app settings..."
az functionapp config appsettings set -g "$resourceGroupName" -n "$functionAppName" \
    --settings "DATAVERSE_ENVIRONMENT_URL=$dataset" -o none
azd env set DATAVERSE_ENVIRONMENT_URL "$dataset" 2>/dev/null || true

# --- Authorize the Dataverse connection (OAuth consent) ----------------------
echo ""
echo "Authorizing Microsoft Dataverse connection..."

currentStatus=$(az connector-namespace connection show \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$connectorNamespaceConnectionName" \
    --query "properties.overallStatus" -o tsv 2>/dev/null || true)

if [ "$(echo "$currentStatus" | tr '[:upper:]' '[:lower:]')" = "connected" ]; then
    echo "   already Connected; skipping consent flow"
else
    echo "-> A browser tab will open. Sign in with an account that has access to the Dataverse environment."
    consentParams="[{parameterName:token,redirectUrl:'https://portal.azure.com'}]"
    link=""
    for attempt in 1 2 3 4 5; do
        link=$(az connector-namespace connection list-consent-links \
            -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
            --connection-name "$connectorNamespaceConnectionName" \
            --parameters "$consentParams" \
            --query "value[0].link" -o tsv 2>/dev/null || true)

        if [ -z "$link" ]; then
            link=$(az connector-namespace connection list-consent-links \
                -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
                --connection-name "$connectorNamespaceConnectionName" \
                --parameters "$consentParams" \
                --query "link" -o tsv 2>/dev/null || true)
        fi

        [ -n "$link" ] && break
        echo "   list-consent-links attempt ${attempt} failed; retrying in 5s..."
        sleep 5
    done

    if [ -z "$link" ]; then
        echo "ERROR: could not obtain consent link after retries."
        exit 1
    fi

    echo "   opening browser for OAuth consent..."
    echo "   (if no tab opens, paste this URL manually: $link)"
    xdg-open "$link" 2>/dev/null || open "$link" 2>/dev/null || echo "   (could not open browser — please open the URL above manually)"

    deadline=$((SECONDS + 300))
    authorized=false
    while [ $SECONDS -lt $deadline ]; do
        sleep 5
        status=$(az connector-namespace connection show \
            -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
            -n "$connectorNamespaceConnectionName" \
            --query "properties.overallStatus" -o tsv 2>/dev/null || true)
        echo "   status: ${status:-unknown}"
        if [ "$(echo "$status" | tr '[:upper:]' '[:lower:]')" = "connected" ]; then
            authorized=true
            break
        fi
    done

    if [ "$authorized" != "true" ]; then
        echo "ERROR: Connection did not reach 'Connected' status within 5 minutes."
        exit 1
    fi
    echo "   Connection authenticated"
fi

# --- Create Connector Namespace trigger config -------------------------------
echo ""
echo "Fetching connector extension key for $functionAppName..."
connectorExtensionKey=$(az functionapp keys list -g "$resourceGroupName" -n "$functionAppName" --query "systemKeys.connector_extension" -o tsv)
if [ -z "$connectorExtensionKey" ]; then
    echo "ERROR: could not fetch connector_extension system key."
    exit 1
fi

functionName="OnDataverseRowChanged"
operationName="GetOnNewItems_V2"
triggerName="${connectorNamespaceConnectionName}-$(echo "$functionName" | tr '[:upper:]' '[:lower:]')"
# Read the app's real default host rather than assuming ".azurewebsites.net" (which differs for
# custom domains and sovereign clouds, e.g. .azurewebsites.us / .chinacloudsites.cn). Query at the
# ARM resource level — `az functionapp show` can return empty host fields for Flex Consumption apps.
functionHost=$(az resource show -g "$resourceGroupName" -n "$functionAppName" --resource-type "Microsoft.Web/sites" --query "properties.defaultHostName" -o tsv)
if [ -z "$functionHost" ]; then
    echo "ERROR: could not resolve defaultHostName for $functionAppName."
    exit 1
fi
callbackUrl="https://${functionHost}/runtime/webhooks/connector?functionName=${functionName}&code=${connectorExtensionKey}"
notifFile="${SCRIPT_DIR}/.notification-details.${RANDOM}.${RANDOM}.json"
_notif_files+=("$notifFile")
printf '{"callbackUrl":"%s"}' "$callbackUrl" > "$notifFile"

echo ""
echo "Creating trigger '${triggerName}' for ${functionName} (${operationName})..."

az connector-namespace trigger delete \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$triggerName" --yes 2>/dev/null || true

az connector-namespace trigger create \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$triggerName" \
    --connection-details "{connectionName:${connectorNamespaceConnectionName},connectorName:commondataservice}" \
    --operation-name "$operationName" \
    --parameters "[{name:dataset,value:'${dataset}'},{name:table,value:'${tableName}'}]" \
    --notification-details "@${notifFile}" \
    --description "When a new row is added" \
    --metadata "{destinationType:functionApp,functionAppName:${functionAppName},functionAppResourceGroup:${resourceGroupName},functionAppSubscriptionId:${AZURE_SUBSCRIPTION_ID},functionName:${functionName},recurrenceFrequency:Minute,recurrenceInterval:'5'}" \
    -o none

rm -f "$notifFile"

echo ""
echo "Post-deployment configuration complete."
echo "Add a new '${tableName}' row in '${environmentUrl}' to fire the trigger (allow one polling interval)."
echo "Tail logs: az functionapp log tail -g $resourceGroupName -n $functionAppName"
echo ""
