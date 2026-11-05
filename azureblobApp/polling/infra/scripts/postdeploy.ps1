param([switch] $ForceLocalSettings)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')

Write-Host 'Post-deployment configuration...' -ForegroundColor Yellow

$extensionName = az extension show --name connector-namespace --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extensionName) {
    throw "The 'connector-namespace' Azure CLI extension is required."
}

$outputJson = azd env get-values --output json
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to read deployment outputs.'
}

$outputs = ($outputJson -join "`n") | ConvertFrom-Json
if ($outputs -isnot [System.Management.Automation.PSCustomObject]) {
    throw 'Deployment outputs must be a JSON object.'
}

foreach ($key in @('resourceGroupName', 'connectorNamespaceName', 'connectorNamespaceConnectionName', 'connectorPollingEndpoint')) {
    $value = $outputs.$key
    if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value) -or $value -eq 'null') {
        throw "Deployment output '$key' must be a nonempty string."
    }
}

$resourceGroupName = $outputs.resourceGroupName
$connectorNamespaceName = $outputs.connectorNamespaceName
$connectorNamespaceConnectionName = $outputs.connectorNamespaceConnectionName
$triggerConfigSettings = $outputs.triggerConfigSettings
if ($triggerConfigSettings -is [string]) {
    $triggerConfigSettings = $triggerConfigSettings | ConvertFrom-Json
}

if ($triggerConfigSettings -isnot [System.Management.Automation.PSCustomObject]) {
    throw "Deployment output 'triggerConfigSettings' must be a JSON object or a JSON-encoded object."
}

$triggerName = $triggerConfigSettings.OnAzureBlobUpdatedFileTriggerConfigName
if ($triggerName -isnot [string] -or [string]::IsNullOrWhiteSpace($triggerName) -or $triggerName -eq 'null') {
    throw "Trigger config setting 'OnAzureBlobUpdatedFileTriggerConfigName' must be a nonempty string."
}

$values = [ordered]@{
    AzureWebJobsStorage = 'UseDevelopmentStorage=true'
    FUNCTIONS_WORKER_RUNTIME = 'python'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'
    ConnectorNamespace__pollingEndpoint = $outputs.connectorPollingEndpoint
    OnAzureBlobUpdatedFileTriggerConfigName = $triggerName
}
Write-LocalSettings $values -ForceLocalSettings:$ForceLocalSettings

Write-Host 'Authorizing Azure Blob Storage connection...' -ForegroundColor Yellow
$currentStatus = az connector-namespace connection show `
    -g $resourceGroupName --namespace $connectorNamespaceName `
    -n $connectorNamespaceConnectionName `
    --query 'properties.overallStatus' -o tsv
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to read connection status.'
}

if ($currentStatus -eq 'Connected') {
    Write-Host 'Connection is already authorized.' -ForegroundColor Green
} else {
    Write-Host 'Sign in with the same user granted source storage access during provisioning.' -ForegroundColor Cyan
    $consentLink = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $consentLink = az connector-namespace connection list-consent-links `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            --connection-name $connectorNamespaceConnectionName `
            --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
            --query 'value[0].link' -o tsv 2>$null
        if ($LASTEXITCODE -ne 0) {
            $consentLink = $null
        }

        if (-not $consentLink -or $consentLink -eq 'null') {
            $consentLink = az connector-namespace connection list-consent-links `
                -g $resourceGroupName --namespace $connectorNamespaceName `
                --connection-name $connectorNamespaceConnectionName `
                --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
                --query 'link' -o tsv 2>$null
            if ($LASTEXITCODE -ne 0) {
                $consentLink = $null
            }
        }

        if ($consentLink -and $consentLink -ne 'null') {
            break
        }

        if ($attempt -lt 5) {
            Write-Host "Consent link attempt $attempt failed. Retrying in 5 seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }

    if (-not $consentLink -or $consentLink -eq 'null') {
        throw 'Failed to create consent link.'
    }

    Write-Host "Consent URL: $consentLink" -ForegroundColor Cyan
    try {
        Start-Process $consentLink | Out-Null
    } catch {
        Write-Host 'Unable to open a browser. Open the consent URL manually.' -ForegroundColor Yellow
    }

    $deadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Seconds 3
        $currentStatus = az connector-namespace connection show `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $connectorNamespaceConnectionName `
            --query 'properties.overallStatus' -o tsv
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to read connection status.'
        }

        Write-Host "Connection status: $currentStatus" -ForegroundColor Cyan
        if ($currentStatus -eq 'Connected') {
            break
        }
    } while ((Get-Date) -lt $deadline)

    if ($currentStatus -ne 'Connected') {
        throw 'Timed out waiting for the connection to reach Connected status.'
    }
}

Write-Host 'Done. The Azure Blob connection is authorized; Bicep manages the Poll trigger.' -ForegroundColor Green