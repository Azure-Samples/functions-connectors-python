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
$dataverseEnvironmentUrl  = $outputs.dataverseEnvironmentUrl
$dataverseEnvironmentName = $outputs.dataverseEnvironmentName
$tableName                = $outputs.dataverseTableName

if (-not $resourceGroupName -or -not $connectorNamespaceName -or -not $connectorNamespaceConnectionName -or -not $functionAppName) {
    Write-Host "ERROR: required azd outputs missing. Run 'azd provision' first." -ForegroundColor Red
    exit 1
}

# --- Resolve the org URL from the environment friendly name (Global Discovery) ---
# If DATAVERSE_ENVIRONMENT_URL is not set but a friendly name is, look up the org
# URL via the Dataverse Global Discovery Service using the signed-in az identity.
if (-not $dataverseEnvironmentUrl -and $dataverseEnvironmentName) {
    Write-Host "Resolving org URL for environment '$dataverseEnvironmentName' via Global Discovery..." -ForegroundColor Cyan
    $discoResource = 'https://globaldisco.crm.dynamics.com'
    $token = az account get-access-token --resource $discoResource --query accessToken -o tsv 2>$null
    if (-not $token) {
        Write-Host "ERROR: could not obtain a Dataverse token. Ensure your 'az login' identity has access to the" -ForegroundColor Red
        Write-Host "       environment, or set DATAVERSE_ENVIRONMENT_URL explicitly and re-provision." -ForegroundColor Red
        exit 1
    }
    try {
        $resp = Invoke-RestMethod -Uri "$discoResource/api/discovery/v2.0/Instances" `
            -Headers @{ Authorization = "Bearer $token" } -Method Get
    } catch {
        Write-Host "ERROR: Global Discovery request failed: $_" -ForegroundColor Red
        exit 1
    }
    $match = @($resp.value | Where-Object { $_.FriendlyName -eq $dataverseEnvironmentName })
    if ($match.Count -eq 0) {
        Write-Host "ERROR: no environment named '$dataverseEnvironmentName' is visible to your identity." -ForegroundColor Red
        Write-Host "Environments available to you:" -ForegroundColor Yellow
        $resp.value | ForEach-Object { Write-Host "  - $($_.FriendlyName)  ->  $($_.Url)" }
        exit 1
    }
    if ($match.Count -gt 1) {
        Write-Host "   multiple environments named '$dataverseEnvironmentName'; using the first." -ForegroundColor Yellow
    }
    $dataverseEnvironmentUrl = $match[0].Url.TrimEnd('/')
    Write-Host "   resolved: $dataverseEnvironmentUrl" -ForegroundColor Green
}

if (-not $dataverseEnvironmentUrl) {
    Write-Host "ERROR: Dataverse environment is not set. Provide the friendly name (auto-resolved) or the URL:" -ForegroundColor Red
    Write-Host "  azd env set DATAVERSE_ENVIRONMENT_NAME 'Contoso (default)'" -ForegroundColor Red
    Write-Host "  # or" -ForegroundColor Red
    Write-Host "  azd env set DATAVERSE_ENVIRONMENT_URL 'https://<your-org>.crm.dynamics.com'" -ForegroundColor Red
    Write-Host "  azd provision" -ForegroundColor Red
    exit 1
}

if (-not $tableName) { $tableName = 'accounts' }

# GetOnNewItems_V2 uses the org URL as the "dataset" value (no trailing slash).
$dataset = $dataverseEnvironmentUrl.TrimEnd('/')

Write-Host "Environment : $dataverseEnvironmentUrl$(if ($dataverseEnvironmentName) { " ($dataverseEnvironmentName)" })" -ForegroundColor DarkGray
Write-Host "Dataset     : $dataset" -ForegroundColor DarkGray
Write-Host "Table       : $tableName" -ForegroundColor DarkGray

# Persist the resolved org URL as an app setting so the ListDataverseRows action
# (which reads DATAVERSE_ENVIRONMENT_URL directly) uses the org URL as its dataset,
# matching the trigger. Without this, a friendly-name-only config leaves the setting
# empty and the action would send the name, which the connector rejects (400).
Write-Host "Persisting resolved org URL to $functionAppName app settings..." -ForegroundColor Cyan
az functionapp config appsettings set -g $resourceGroupName -n $functionAppName `
    --settings "DATAVERSE_ENVIRONMENT_URL=$dataset" -o none
azd env set DATAVERSE_ENVIRONMENT_URL $dataset 2>$null | Out-Null

# --- Authorize the Dataverse connection (OAuth consent) ----------------------
Write-Host ""
Write-Host "Authorizing Microsoft Dataverse connection..." -ForegroundColor Yellow

$currentStatus = az connector-namespace connection show `
    -g $resourceGroupName --namespace $connectorNamespaceName `
    -n $connectorNamespaceConnectionName `
    --query "properties.overallStatus" -o tsv 2>$null

if ($currentStatus -and $currentStatus.ToLower() -eq 'connected') {
    Write-Host "   already Connected; skipping consent flow" -ForegroundColor Green
} else {
    Write-Host "-> A browser tab will open. Sign in with an account that has access to the Dataverse environment." -ForegroundColor Cyan

    $consentParameters = "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]"
    $link = $null

    for ($i = 0; $i -lt 5; $i++) {
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

# --- Create Connector Namespace trigger config -------------------------------
Write-Host ""
Write-Host "Fetching connector extension key for $functionAppName..." -ForegroundColor Cyan
$connectorExtensionKey = (az functionapp keys list -g $resourceGroupName -n $functionAppName --query "systemKeys.connector_extension" -o tsv)
if (-not $connectorExtensionKey) {
    Write-Host "ERROR: could not fetch connector_extension system key from $functionAppName." -ForegroundColor Red
    exit 1
}

$functionName  = 'OnDataverseRowChanged'
$operationName = 'GetOnNewItems_V2'
$triggerName   = "$connectorNamespaceConnectionName-$($functionName.ToLower())"
# Read the app's real default host rather than assuming ".azurewebsites.net" (which differs for
# custom domains and sovereign clouds, e.g. .azurewebsites.us / .chinacloudsites.cn).
$functionHost  = (az functionapp show -g $resourceGroupName -n $functionAppName --query "defaultHostName" -o tsv)
if (-not $functionHost) {
    Write-Host "ERROR: could not resolve defaultHostName for $functionAppName." -ForegroundColor Red
    exit 1
}
$callbackUrl   = "https://$functionHost/runtime/webhooks/connector?functionName=$functionName&code=$connectorExtensionKey"
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
        --connection-details "{connectionName:$connectorNamespaceConnectionName,connectorName:commondataservice}" `
        --operation-name $operationName `
        --parameters "[{name:dataset,value:'$dataset'},{name:table,value:'$tableName'}]" `
        --notification-details "@$notifFile" `
        --description "When a new row is added" `
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
Write-Host "Add a new '$tableName' row in '$dataverseEnvironmentUrl' to fire the trigger (allow one polling interval)." -ForegroundColor Green
Write-Host "Tail logs: az functionapp log tail -g $resourceGroupName -n $functionAppName" -ForegroundColor Green
Write-Host ""
