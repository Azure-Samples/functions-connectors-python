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

Write-Host 'Waiting for the managed-identity Azure Blob connection...' -ForegroundColor Yellow
for ($attempt = 1; $attempt -le 100; $attempt++) {
    $connectionJson = az connector-namespace connection show `
        -g $resourceGroupName --namespace $connectorNamespaceName `
        -n $connectorNamespaceConnectionName -o json 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to read connection status.'
    }

    try { $connection = ($connectionJson -join "`n") | ConvertFrom-Json -ErrorAction Stop }
    catch { throw 'Invalid connection configuration response.' }
    if ($connection -isnot [System.Management.Automation.PSCustomObject] -or
        $connection.properties.parameterValueSet.name -cne 'managedIdentityAuth') {
        throw 'Azure Blob connection must use managedIdentityAuth. Reprovision the separate -mi connection; an existing OAuth connection cannot migrate to managed identity.'
    }

    $currentStatus = $connection.properties.overallStatus
    if ($currentStatus -is [string] -and $currentStatus.Trim() -in @('Connected', 'Ready')) {
        break
    }
    if ($currentStatus -is [string] -and $currentStatus.Trim() -eq 'Error') {
        throw 'The managed-identity Blob connection is in Error status. Verify the namespace connection access policy and container Storage Blob Data Reader grant. Allow RBAC propagation, then rerun the hook.'
    }
    if ($attempt -eq 100) {
        throw 'Timed out waiting for the managed-identity Blob connection to reach Connected or Ready status. Verify the namespace connection access policy and container Storage Blob Data Reader grant. Allow RBAC propagation, then rerun the hook.'
    }

    Start-Sleep -Seconds 3
}

Write-Host 'Done. The managed-identity Azure Blob connection is ready; Bicep manages the Poll trigger.' -ForegroundColor Green