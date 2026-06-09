# Post-deployment configuration for the azureblobApp (Python).
#
# The Azure Blob connection uses Entra ID (OAuth) authentication.
# This script authorizes the connection via interactive consent,
# then creates the trigger config pointing to the function's
# connector webhook URL.

Write-Host "Post-deployment configuration..." -ForegroundColor Yellow

# --- Pre-flight: verify the connector-namespace CLI extension is installed ----
if (-not (az extension show --name connector-namespace --query name -o tsv 2>$null)) {
    Write-Host "ERROR: The 'connector-namespace' Azure CLI extension is required." -ForegroundColor Red
    Write-Host "Install: irm https://aka.ms/connector-namespace-cli-install-ps | iex" -ForegroundColor Red
    exit 1
}

# --- Read azd outputs --------------------------------------------------------
$outputs = azd env get-values --output json | ConvertFrom-Json

$resourceGroupName        = $outputs.resourceGroupName
$connectorNamespaceName   = $outputs.connectorNamespaceName
$connectorNamespaceConnectionName = $outputs.connectorNamespaceConnectionName
$functionAppName          = $outputs.functionAppName
$subscriptionId           = $outputs.AZURE_SUBSCRIPTION_ID
$monitoredStorageAccountName = $outputs.monitoredStorageAccountName

if (-not $resourceGroupName -or -not $connectorNamespaceName -or -not $connectorNamespaceConnectionName -or -not $functionAppName) {
    Write-Host "ERROR: required azd outputs missing. Run 'azd provision' first." -ForegroundColor Red
    exit 1
}

# --- Authorize the Azure Blob connection (OAuth consent) --------------------
Write-Host ""
Write-Host "Authorizing Azure Blob Storage connection..." -ForegroundColor Yellow

$currentStatus = az connector-namespace connection show `
    -g $resourceGroupName --namespace $connectorNamespaceName `
    -n $connectorNamespaceConnectionName `
    --query "properties.overallStatus" -o tsv 2>$null

if ($currentStatus -and $currentStatus.ToLower() -eq 'connected') {
    Write-Host "   already Connected; skipping consent flow" -ForegroundColor Green
} else {
    $consentParameters = "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]"
    $consentJson = $null
    $link = $null

    for ($i = 0; $i -lt 5; $i++) {
        $consentJson = az connector-namespace connection list-consent-links `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            --connection-name $connectorNamespaceConnectionName `
            --parameters $consentParameters `
            -o json 2>$null | Out-String
        if ($LASTEXITCODE -eq 0 -and $consentJson) {
            $link = az connector-namespace connection list-consent-links `
                -g $resourceGroupName --namespace $connectorNamespaceName `
                --connection-name $connectorNamespaceConnectionName `
                --parameters $consentParameters `
                --query "value[0].link" -o tsv 2>$null
            if (-not $link) {
                $link = az connector-namespace connection list-consent-links `
                    -g $resourceGroupName --namespace $connectorNamespaceName `
                    --connection-name $connectorNamespaceConnectionName `
                    --parameters $consentParameters `
                    --query "link" -o tsv 2>$null
            }
            if ($link) { break }
        }

        Write-Host "   list-consent-links attempt $($i + 1) failed; retrying in 5s..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }

    if (-not $link) {
        Write-Host "ERROR: could not obtain consent link after retries." -ForegroundColor Red
        exit 1
    }

    Write-Host "   opening browser for OAuth consent..." -ForegroundColor Cyan
    Write-Host "   (if no tab opens, paste this URL manually: $link)" -ForegroundColor Cyan
    try { Start-Process $link | Out-Null } catch { Write-Host "   Start-Process failed: $_" -ForegroundColor Yellow }

    $deadline = (Get-Date).AddMinutes(5)
    $authorized = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        $status = az connector-namespace connection show `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $connectorNamespaceConnectionName `
            --query "properties.overallStatus" -o tsv 2>$null
        Write-Host "   status: $status"
        if ($status -and $status.ToLower() -eq 'connected') {
            $authorized = $true
            break
        }
    }

    if (-not $authorized) {
        Write-Host "ERROR: Connection did not reach 'Connected' status within 5 minutes." -ForegroundColor Red
        exit 1
    }
    Write-Host "   Connection authenticated" -ForegroundColor Green
}

# --- Container path for the trigger ----------------------------------------
$containerName  = $outputs.monitoredContainerName
if (-not $containerName) { $containerName = 'connector-input' }
$urlEncodedPath = "%2f$containerName"
$folderIdBytes  = [System.Text.Encoding]::UTF8.GetBytes($urlEncodedPath)
$folderId       = [Convert]::ToBase64String($folderIdBytes)

Write-Host "Container '$containerName' -> folderId '$folderId'" -ForegroundColor DarkGray

# --- Create Connector Namespace trigger config -------------------------------
Write-Host ""
Write-Host "Fetching connector extension key for $functionAppName..." -ForegroundColor Cyan
$connectorExtensionKey = (az functionapp keys list -g $resourceGroupName -n $functionAppName --query "systemKeys.connector_extension" -o tsv)
if (-not $connectorExtensionKey) {
    Write-Host "ERROR: could not fetch connector_extension system key from $functionAppName." -ForegroundColor Red
    exit 1
}

$functionName  = 'OnAzureBlobUpdatedFile'
$operationName = 'OnUpdatedFiles_V2'
$triggerName   = "$connectorNamespaceConnectionName-$($functionName.ToLower())"
$callbackUrl   = "https://$functionAppName.azurewebsites.net/runtime/webhooks/connector?functionName=$functionName&code=$connectorExtensionKey"
$notifFile     = Join-Path $PSScriptRoot ".notification-details-$([System.Guid]::NewGuid().ToString('N')).json"
@{ callbackUrl = $callbackUrl } | ConvertTo-Json -Compress | Set-Content -Path $notifFile -NoNewline

Write-Host "Creating trigger '$triggerName' for $functionName ($operationName)..." -ForegroundColor Yellow

try {
    az connector-namespace trigger delete `
        -g $resourceGroupName --namespace $connectorNamespaceName `
        -n $triggerName --yes 2>$null | Out-Null

    az connector-namespace trigger create `
        -g $resourceGroupName --namespace $connectorNamespaceName `
        -n $triggerName `
        --connection-details "{connectionName:$connectorNamespaceConnectionName,connectorName:azureblob}" `
        --operation-name $operationName `
        --parameters "[{name:dataset,value:'$monitoredStorageAccountName'},{name:folderId,value:'$folderId'}]" `
        --notification-details "@$notifFile" `
        --description "When a blob is added or modified (properties only) (V2)" `
        --metadata "{destinationType:functionApp,functionAppName:$functionAppName,functionAppResourceGroup:$resourceGroupName,functionAppSubscriptionId:$subscriptionId,functionName:$functionName,recurrenceFrequency:Minute,recurrenceInterval:'5'}" `
        -o none

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create trigger config for $functionName." -ForegroundColor Red
        exit 1
    }
}
finally {
    Remove-Item $notifFile -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Post-deployment configuration complete." -ForegroundColor Green
Write-Host "Upload blobs to the '$containerName' container in storage account '$monitoredStorageAccountName' to fire the trigger." -ForegroundColor Green
Write-Host "Tail logs: az functionapp log tail -g $resourceGroupName -n $functionAppName" -ForegroundColor Green
Write-Host ""
