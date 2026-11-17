$ErrorActionPreference = 'Stop'

# Runs before the triggers layer so Poll triggers are created enabled on an authorized connection.
$extensionName = az extension show --name connector-namespace --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extensionName) {
    throw "The 'connector-namespace' Azure CLI extension is required."
}

$outputJson = azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Failed to read base layer outputs.' }
$outputs = ($outputJson -join "`n") | ConvertFrom-Json
foreach ($key in @('AZURE_SUBSCRIPTION_ID', 'resourceGroupName', 'connectorNamespaceName', 'connectorNamespaceConnectionName')) {
    $value = $outputs.$key
    if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value) -or $value -eq 'null') {
        throw "Base layer output '$key' must be a nonempty string. Run 'azd provision base' first."
    }
}
$resourceGroupName = $outputs.resourceGroupName
$connectorNamespaceName = $outputs.connectorNamespaceName
$connectorNamespaceConnectionName = $outputs.connectorNamespaceConnectionName

function Get-ConnectionStatus {
    $status = az connector-namespace connection show `
        --subscription $outputs.AZURE_SUBSCRIPTION_ID `
        -g $resourceGroupName --namespace $connectorNamespaceName `
        -n $connectorNamespaceConnectionName --query 'properties.overallStatus' -o tsv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to read connection status.' }
    return $status
}

Write-Host 'Authorizing OneDrive for Business connection...'
if ((Get-ConnectionStatus) -ne 'Connected') {
    $consentLink = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $consentLink = az connector-namespace connection list-consent-links `
            --subscription $outputs.AZURE_SUBSCRIPTION_ID `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            --connection-name $connectorNamespaceConnectionName `
            --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
            --query 'value[0].link' -o tsv 2>$null
        if ($LASTEXITCODE -ne 0) { $consentLink = $null }
        if (-not $consentLink -or $consentLink -eq 'null') {
            $consentLink = az connector-namespace connection list-consent-links `
                --subscription $outputs.AZURE_SUBSCRIPTION_ID `
                -g $resourceGroupName --namespace $connectorNamespaceName `
                --connection-name $connectorNamespaceConnectionName `
                --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
                --query 'link' -o tsv 2>$null
            if ($LASTEXITCODE -ne 0) { $consentLink = $null }
        }
        if ($consentLink -and $consentLink -ne 'null') { break }
        if ($attempt -lt 5) { Start-Sleep -Seconds 5 }
    }
    if (-not $consentLink -or $consentLink -eq 'null') { throw 'Failed to create consent link.' }
    Write-Host "Sign in with the account that owns the OneDrive folder: $consentLink"
    try { Start-Process $consentLink | Out-Null }
    catch { Write-Host 'Open the consent URL in your browser.' }

    $deadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Seconds 3
        $status = Get-ConnectionStatus
        if ($status -eq 'Connected') { break }
    } while ((Get-Date) -lt $deadline)
    if ($status -ne 'Connected') { throw 'Timed out waiting for the OneDrive connection to reach Connected status.' }
}

$python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
& $python (Join-Path $PSScriptRoot 'select_folder.py')
if ($LASTEXITCODE -ne 0) { throw 'OneDrive folder selection failed.' }
Write-Host 'Done. The OneDrive connection is authorized; the triggers layer will create the 4 enabled Poll triggers.'
