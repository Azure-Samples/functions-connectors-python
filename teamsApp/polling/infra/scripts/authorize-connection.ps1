$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'validate-triggers.ps1')
Get-Command az, azd -ErrorAction Stop | Out-Null
$extension = az extension show --name connector-namespace --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extension) { throw 'The connector-namespace Azure CLI extension is required.' }
$raw = azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read the azd environment.' }
$outputs = ($raw -join "`n") | ConvertFrom-Json
foreach ($name in @('AZURE_SUBSCRIPTION_ID', 'resourceGroupName', 'connectorNamespaceName', 'connectorNamespaceConnectionName')) {
    if ([string]::IsNullOrWhiteSpace([string]$outputs.$name)) { throw "Missing base layer output $name." }
}

function Get-ConnectionStatus {
    $status = az connector-namespace connection show --subscription $outputs.AZURE_SUBSCRIPTION_ID `
        -g $outputs.resourceGroupName --namespace $outputs.connectorNamespaceName `
        -n $outputs.connectorNamespaceConnectionName --query properties.overallStatus -o tsv 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$status)) {
        throw 'Could not read the Teams connection status.'
    }
    return ([string]$status).Trim()
}

if ((Get-ConnectionStatus) -ne 'Connected') {
    $link = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $rawConsent = az connector-namespace connection list-consent-links --subscription $outputs.AZURE_SUBSCRIPTION_ID `
            -g $outputs.resourceGroupName --namespace $outputs.connectorNamespaceName `
            --connection-name $outputs.connectorNamespaceConnectionName `
            --parameters "[{parameterName:token,redirectUrl:'https://connectors.azure.com'}]" -o json 2>$null
        if ($LASTEXITCODE -eq 0) {
            $consent = ($rawConsent -join "`n") | ConvertFrom-Json
            $link = if ($consent.value) { $consent.value[0].link } else { $consent.link }
        }
        if ($link -and $link -ne 'null') { break }
        if ($attempt -lt 5) { Start-Sleep -Seconds 5 }
    }
    if (-not $link -or $link -eq 'null') { throw 'Could not obtain a Teams consent link.' }
    $uri = [uri]$link
    if (-not $uri.IsAbsoluteUri -or $uri.Scheme -ne 'https' -or $uri.UserInfo) { throw 'Invalid Teams consent URL.' }
    Write-Host "Authorize the Teams connection in your browser: $link"
    try { Start-Process $link | Out-Null }
    catch { Write-Host 'Open the consent URL shown above in your browser.' }
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-ConnectionStatus) -ne 'Connected') {
        if ((Get-Date) -ge $deadline) { throw 'Timed out waiting for Teams OAuth consent.' }
        Start-Sleep -Seconds 3
    }
}

$python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
& $python (Join-Path $PSScriptRoot 'select_sources.py')
if ($LASTEXITCODE -ne 0) { throw 'Teams source selection failed.' }
