Write-Host "Post-deployment configuration..." -ForegroundColor Yellow

if (-not (az extension show --name connector-namespace --query name -o tsv 2>$null)) {
    Write-Host "ERROR: The 'connector-namespace' Azure CLI extension is required." -ForegroundColor Red
    Write-Host "Install: irm https://aka.ms/connector-namespace-cli-install-ps | iex" -ForegroundColor Red
    exit 1
}

$outputs = azd env get-values --output json | ConvertFrom-Json

$resourceGroupName = $outputs.resourceGroupName
$connectorNamespaceName = $outputs.connectorNamespaceName
$connectorNamespaceConnectionName = $outputs.connectorNamespaceConnectionName
$functionAppName = $outputs.functionAppName
$subscriptionId = $outputs.AZURE_SUBSCRIPTION_ID
$sharepointSiteUrl = $outputs.sharepointSiteUrl
$sharepointLibraryName = $outputs.sharepointLibraryName

if (-not $resourceGroupName -or -not $connectorNamespaceName -or -not $connectorNamespaceConnectionName -or -not $functionAppName -or -not $sharepointSiteUrl -or -not $sharepointLibraryName) {
    Write-Host "ERROR: required azd outputs missing. Run 'azd provision' first." -ForegroundColor Red
    exit 1
}

Write-Host "Fetching connector extension key for $functionAppName..." -ForegroundColor Cyan
$connectorExtensionKey = az functionapp keys list -g $resourceGroupName -n $functionAppName --query "systemKeys.connector_extension" -o tsv
if (-not $connectorExtensionKey) {
    Write-Host "ERROR: could not fetch connector_extension system key from $functionAppName." -ForegroundColor Red
    exit 1
}

Write-Host "Creating Connector Namespace trigger configs..." -ForegroundColor Yellow
Write-Host "  SharePoint site: $sharepointSiteUrl" -ForegroundColor Cyan
Write-Host "  Library: $sharepointLibraryName" -ForegroundColor Cyan

$triggerConfigs = @(
    @{
        FunctionName = 'OnSharepointNewFile'
        OperationName = 'GetOnNewFileItems'
        Description = 'When a file is created (properties only)'
    },
    @{
        FunctionName = 'OnSharepointUpdatedFile'
        OperationName = 'GetOnUpdatedFileItems'
        Description = 'When a file is created or modified (properties only)'
    }
)

foreach ($trigger in $triggerConfigs) {
    $functionName = $trigger.FunctionName
    $triggerName = "$connectorNamespaceConnectionName-$($functionName.ToLower())"
    $callbackUrl = "https://$functionAppName.azurewebsites.net/runtime/webhooks/connector?functionName=$functionName&code=$connectorExtensionKey"
    $notifFile = Join-Path $PSScriptRoot ".notification-details-$([System.Guid]::NewGuid().ToString('N')).json"
    @{ callbackUrl = $callbackUrl } | ConvertTo-Json -Compress | Set-Content -Path $notifFile -NoNewline

    Write-Host "  Creating trigger: $($trigger.FunctionName) -> $($trigger.OperationName)" -ForegroundColor Cyan

    try {
        az connector-namespace trigger delete `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $triggerName --yes 2>$null | Out-Null

        az connector-namespace trigger create `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $triggerName `
            --connection-details "{connectionName:$connectorNamespaceConnectionName,connectorName:sharepointonline}" `
            --operation-name $trigger.OperationName `
            --parameters "[{name:dataset,value:'$sharepointSiteUrl'},{name:table,value:'$sharepointLibraryName'}]" `
            --notification-details "@$notifFile" `
            --description $trigger.Description `
            --metadata "{destinationType:functionApp,functionAppName:$functionAppName,functionAppResourceGroup:$resourceGroupName,functionAppSubscriptionId:$subscriptionId,functionName:$functionName,recurrenceFrequency:Minute,recurrenceInterval:'5'}" `
            -o none

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Failed to create trigger config for $($trigger.FunctionName)." -ForegroundColor Red
            exit 1
        }
    }
    finally {
        Remove-Item $notifFile -ErrorAction SilentlyContinue
    }
}

Write-Host "All trigger configs created." -ForegroundColor Green
Write-Host ""
Write-Host "Authorizing sharepointonline connection..." -ForegroundColor Yellow

$currentStatus = az connector-namespace connection show `
    -g $resourceGroupName --namespace $connectorNamespaceName `
    -n $connectorNamespaceConnectionName `
    --query "properties.overallStatus" -o tsv 2>$null

if ($currentStatus -eq "Connected") {
    Write-Host "Connection is already authorized." -ForegroundColor Green
} else {
    Write-Host "-> A browser tab will open. Sign in with the account that has access to the SharePoint site." -ForegroundColor Cyan

    $consentLink = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $consentLink = az connector-namespace connection list-consent-links `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            --connection-name $connectorNamespaceConnectionName `
            --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
            --query "value[0].link" -o tsv 2>$null

        if (-not $consentLink) {
            $consentLink = az connector-namespace connection list-consent-links `
                -g $resourceGroupName --namespace $connectorNamespaceName `
                --connection-name $connectorNamespaceConnectionName `
                --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
                --query "link" -o tsv 2>$null
        }

        if ($consentLink) {
            break
        }

        if ($attempt -lt 5) {
            Write-Host "list-consent-links attempt $attempt failed. Retrying in 5 seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }

    if (-not $consentLink) {
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
            --query "properties.overallStatus" -o tsv 2>$null

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
Write-Host "Done. Both SharePoint triggers are configured." -ForegroundColor Green
Write-Host "Tail logs: az functionapp log tail -g $resourceGroupName -n $functionAppName" -ForegroundColor Green
Write-Host ""
