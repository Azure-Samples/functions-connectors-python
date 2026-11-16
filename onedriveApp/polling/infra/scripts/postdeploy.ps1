param([switch] $ForceLocalSettings)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')

Write-Host 'Post-deployment configuration...'

$extensionName = az extension show --name connector-namespace --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extensionName) {
    throw "The 'connector-namespace' Azure CLI extension is required."
}

$outputJson = azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Failed to read deployment outputs.' }
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

$values = [ordered]@{
    AzureWebJobsStorage = 'UseDevelopmentStorage=true'
    FUNCTIONS_WORKER_RUNTIME = 'python'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'
    ConnectorNamespace__pollingEndpoint = $outputs.connectorPollingEndpoint
}
foreach ($functionName in @('OnOneDriveNewFile', 'OnOneDriveUpdatedFile', 'OnOneDriveNewFileContent', 'OnOneDriveUpdatedFileContent')) {
    $key = "${functionName}TriggerConfigName"
    $triggerName = $triggerConfigSettings.$key
    if ($triggerName -isnot [string] -or [string]::IsNullOrWhiteSpace($triggerName) -or $triggerName -eq 'null') {
        throw "Trigger config setting '$key' must be a nonempty string."
    }
    $values[$key] = $triggerName
}

Write-LocalSettings $values -ForceLocalSettings:$ForceLocalSettings

Write-Host 'Done. local.settings.json is ready for local runs; the enabled Poll triggers were created by the triggers layer.'
