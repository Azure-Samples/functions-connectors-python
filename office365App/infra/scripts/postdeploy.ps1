Write-Host "Post-deployment configuration..." -ForegroundColor Yellow

if (-not (az extension show --name connector-namespace --query name -o tsv 2>$null)) {
    Write-Host "ERROR: The 'connector-namespace' Azure CLI extension is required." -ForegroundColor Red
    Write-Host "Install: irm https://aka.ms/connector-namespace-cli-install-ps | iex" -ForegroundColor Red
    exit 1
}

# Outputs from azd
$outputs = azd env get-values --output json | ConvertFrom-Json

$resourceGroupName = $outputs.resourceGroupName
$connectorNamespaceName = $outputs.connectorNamespaceName
$connectorNamespaceConnectionName = $outputs.connectorNamespaceConnectionName
$functionAppName = $outputs.functionAppName
$subscriptionId = $outputs.AZURE_SUBSCRIPTION_ID

# Fetch the connector extension system key
Write-Host "Fetching connector extension key for $functionAppName..." -ForegroundColor Cyan
$connectorExtensionKey = az functionapp keys list -g $resourceGroupName -n $functionAppName --query "systemKeys.connector_extension" -o tsv

# --- Helper: create a trigger config on the Connector Namespace ---
function New-TriggerConfig {
    param(
        [Parameter(Mandatory)] [string] $FunctionName,
        [Parameter(Mandatory)] [string] $OperationName,
        [Parameter(Mandatory)] [string] $Description,
        [object[]] $Parameters = @()
    )

    $triggerName = "$connectorNamespaceConnectionName-$($FunctionName.ToLower())"
    $callbackUrl = "https://$functionAppName.azurewebsites.net/runtime/webhooks/connector?functionName=$FunctionName"
    $connectionDetails = "{connectionName:$connectorNamespaceConnectionName,connectorName:office365}"
    $parametersShorthand = "[" + (($Parameters | ForEach-Object { "{name:$($_.name),value:'$($_.value)'}" }) -join ",") + "]"
    $notifFile = Join-Path $PSScriptRoot ".notification-details-$([System.Guid]::NewGuid().ToString('N')).json"
    @{
        callbackUrl = $callbackUrl
        authentication = @{
            type = "QueryString"
            name = "code"
            value = $connectorExtensionKey
        }
    } | ConvertTo-Json -Depth 3 -Compress | Set-Content -Path $notifFile -NoNewline

    Write-Host "  Creating trigger: $FunctionName -> $OperationName" -ForegroundColor Cyan

    try {
        az connector-namespace trigger delete `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $triggerName --yes 2>$null | Out-Null

        az connector-namespace trigger create `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $triggerName `
            --connection-details $connectionDetails `
            --operation-name $OperationName `
            --parameters $parametersShorthand `
            --notification-details "@$notifFile" `
            --description $Description `
            --metadata "{destinationType:functionApp,functionAppName:$functionAppName,functionAppResourceGroup:$resourceGroupName,functionAppSubscriptionId:$subscriptionId,functionName:$FunctionName,recurrenceFrequency:Minute,recurrenceInterval:'5'}" `
            -o none | Out-Null

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Failed to create trigger config for $FunctionName." -ForegroundColor Red
            exit 1
        }
    }
    finally {
        Remove-Item $notifFile -ErrorAction SilentlyContinue
    }
}

# --- Create trigger configs for all 5 functions ---
Write-Host "Creating Connector Namespace trigger configs..." -ForegroundColor Yellow

New-TriggerConfig `
    -FunctionName "OnNewEmail" `
    -OperationName "OnNewEmailV3" `
    -Description "When a new email arrives" `
    -Parameters @(
        @{ name = "folderPath"; value = "Inbox" }
        @{ name = "importance"; value = "High" }
    )

New-TriggerConfig `
    -FunctionName "OnFlaggedEmail" `
    -OperationName "OnFlaggedEmailV4" `
    -Description "When an email is flagged" `
    -Parameters @(
        @{ name = "folderPath"; value = "Inbox" }
    )

New-TriggerConfig `
    -FunctionName "OnNewMentionMeEmail" `
    -OperationName "OnNewMentionMeEmailV3" `
    -Description "When a new email mentioning me arrives" `
    -Parameters @(
        @{ name = "folderPath"; value = "Inbox" }
    )

New-TriggerConfig `
    -FunctionName "OnNewCalendarEvent" `
    -OperationName "CalendarGetOnNewItemsV3" `
    -Description "When a new calendar event is created" `
    -Parameters @(
        @{ name = "table"; value = "Calendar" }
    )

New-TriggerConfig `
    -FunctionName "OnUpcomingEvent" `
    -OperationName "OnUpcomingEventsV3" `
    -Description "When an upcoming event is starting soon" `
    -Parameters @(
        @{ name = "table"; value = "Calendar" }
    )

Write-Host "All trigger configs created." -ForegroundColor Green

Write-Host ""
Write-Host "Authorizing office365 connection..." -ForegroundColor Yellow

$currentStatus = az connector-namespace connection show `
    -g $resourceGroupName --namespace $connectorNamespaceName `
    -n $connectorNamespaceConnectionName `
    --query "properties.overallStatus" -o tsv

if ($currentStatus -eq "Connected") {
    Write-Host "Connection is already authorized." -ForegroundColor Green
} else {
    Write-Host "-> A browser tab will open. Sign in with the mailbox account whose Inbox you want to monitor." -ForegroundColor Cyan

    $consentLink = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $consentLink = az connector-namespace connection list-consent-links `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            --connection-name $connectorNamespaceConnectionName `
            --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
            --query "value[0].link" -o tsv 2>$null

        if (-not $consentLink -or $consentLink -eq "null") {
            $consentLink = az connector-namespace connection list-consent-links `
                -g $resourceGroupName --namespace $connectorNamespaceName `
                --connection-name $connectorNamespaceConnectionName `
                --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
                --query "link" -o tsv 2>$null
        }

        if ($consentLink -and $consentLink -ne "null") {
            break
        }

        if ($attempt -lt 5) {
            Write-Host "listConsentLinks attempt $attempt failed. Retrying in 5 seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }

    if (-not $consentLink -or $consentLink -eq "null") {
        Write-Host "Failed to create consent link." -ForegroundColor Red
        exit 1
    }

    Write-Host "Consent URL: $consentLink" -ForegroundColor Cyan

    try {
        Start-Process $consentLink | Out-Null
    } catch {
        Write-Host "Unable to open a browser automatically. Paste the consent URL into your browser." -ForegroundColor Yellow
    }

    $deadline = (Get-Date).AddMinutes(5)
    $lastPrintedStatus = $currentStatus
    Write-Host "Connection status: $currentStatus" -ForegroundColor Cyan

    do {
        Start-Sleep -Seconds 3
        $currentStatus = az connector-namespace connection show `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $connectorNamespaceConnectionName `
            --query "properties.overallStatus" -o tsv

        if ($currentStatus -ne $lastPrintedStatus) {
            Write-Host "Connection status: $currentStatus" -ForegroundColor Cyan
            $lastPrintedStatus = $currentStatus
        }

        if ($currentStatus -eq "Connected") {
            break
        }
    } while ((Get-Date) -lt $deadline)

    if ($currentStatus -ne "Connected") {
        Write-Host "Timed out waiting for the connection to reach Connected status." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Done. All 5 Office 365 triggers are configured." -ForegroundColor Green
Write-Host "Tail logs: az functionapp log tail -g $resourceGroupName -n $functionAppName" -ForegroundColor Green
Write-Host ""
