#!/usr/bin/env bash
# Post-deployment configuration for the azureblobApp (Python).
#
# The Azure Blob connection uses Entra ID (OAuth) authentication.
# This script authorizes the connection via interactive consent,
# then creates the trigger config pointing at the function's connector webhook URL.

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
: "${monitoredStorageAccountName:?required azd output missing}"

# --- Authorize the Azure Blob connection (OAuth consent) --------------------
echo ""
echo "Authorizing Azure Blob Storage connection..."

currentStatus=$(az connector-namespace connection show \
    -g "$resourceGroupName" --namespace "$connectorNamespaceName" \
    -n "$connectorNamespaceConnectionName" \
    --query "properties.overallStatus" -o tsv 2>/dev/null || true)

if [ "$(echo "$currentStatus" | tr '[:upper:]' '[:lower:]')" = "connected" ]; then
    echo "   already Connected; skipping consent flow"
else
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

# --- Container path for the trigger ----------------------------------------
containerName="${monitoredContainerName:-connector-input}"
urlEncodedPath="%2f${containerName}"
folderId=$(printf '%s' "$urlEncodedPath" | base64)
echo "Container '${containerName}' -> folderId '${folderId}'"

# --- Create Connector Namespace trigger config -------------------------------
echo ""
echo "Fetching connector extension key for $functionAppName..."
connectorExtensionKey=$(az functionapp keys list -g "$resourceGroupName" -n "$functionAppName" --query "systemKeys.connector_extension" -o tsv)
if [ -z "$connectorExtensionKey" ]; then
    echo "ERROR: could not fetch connector_extension system key."
    exit 1
fi

functionName="OnAzureBlobUpdatedFile"
operationName="OnUpdatedFiles_V2"
triggerName="${connectorNamespaceConnectionName}-$(echo "$functionName" | tr '[:upper:]' '[:lower:]')"
callbackUrl="https://${functionAppName}.azurewebsites.net/runtime/webhooks/connector?functionName=${functionName}&code=${connectorExtensionKey}"
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
    --connection-details "{connectionName:${connectorNamespaceConnectionName},connectorName:azureblob}" \
    --operation-name "$operationName" \
    --parameters "[{name:dataset,value:'${monitoredStorageAccountName}'},{name:folderId,value:'${folderId}'}]" \
    --notification-details "@${notifFile}" \
    --description "When a blob is added or modified (properties only) (V2)" \
    --metadata "{destinationType:functionApp,functionAppName:${functionAppName},functionAppResourceGroup:${resourceGroupName},functionAppSubscriptionId:${AZURE_SUBSCRIPTION_ID},functionName:${functionName},recurrenceFrequency:Minute,recurrenceInterval:'5'}" \
    -o none

rm -f "$notifFile"

echo ""
echo "Post-deployment configuration complete."
echo "Upload blobs to the '${containerName}' container in storage account '${monitoredStorageAccountName}' to fire the trigger."
echo "Tail logs: az functionapp log tail -g $resourceGroupName -n $functionAppName"
echo ""
