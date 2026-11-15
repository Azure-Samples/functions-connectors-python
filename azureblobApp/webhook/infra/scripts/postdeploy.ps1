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

foreach ($key in @('resourceGroupName', 'connectorNamespaceName', 'connectorNamespaceConnectionName', 'functionAppName', 'functionAppDefaultHostname', 'AZURE_SUBSCRIPTION_ID', 'monitoredStorageAccountName', 'monitoredContainerName')) {
    $value = $outputs.$key
    if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value) -or $value -eq 'null') {
        throw "Deployment output '$key' must be a nonempty string."
    }
}

$resourceGroupName = $outputs.resourceGroupName
$connectorNamespaceName = $outputs.connectorNamespaceName
$connectorNamespaceConnectionName = $outputs.connectorNamespaceConnectionName
$functionAppName = $outputs.functionAppName
$subscriptionId = $outputs.AZURE_SUBSCRIPTION_ID
$monitoredStorageAccountName = $outputs.monitoredStorageAccountName
$containerName = $outputs.monitoredContainerName
$connectionUri = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.Web/connectorGateways/$connectorNamespaceName/connections/${connectorNamespaceConnectionName}?api-version=2026-05-01-preview"

Write-LocalSettings @{
    FUNCTIONS_WORKER_RUNTIME = 'python'
    AzureWebJobsStorage = 'UseDevelopmentStorage=true'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'
} -ForceLocalSettings:$ForceLocalSettings

Write-Host 'Waiting for the managed-identity Azure Blob connection...' -ForegroundColor Yellow
for ($attempt = 1; $attempt -le 100; $attempt++) {
    $connectionJson = az rest --method get --url $connectionUri --subscription $subscriptionId `
        --query '{properties:{overallStatus:properties.overallStatus,parameterValueSet:{name:properties.parameterValueSet.name}}}' `
        -o json
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

$folderId = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("%2f$containerName"))
$rawTriggers = az connector-namespace trigger list --subscription $subscriptionId -g $resourceGroupName --namespace $connectorNamespaceName --query '[].name' -o json 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Could not list existing webhook trigger configurations.' }
$existingTriggers = ($rawTriggers -join "`n") | ConvertFrom-Json -NoEnumerate
if ($existingTriggers -isnot [array] -or @($existingTriggers | Where-Object { $_ -isnot [string] -or [string]::IsNullOrWhiteSpace($_) }).Count) {
    throw 'Invalid trigger list response.'
}
$connectorExtensionKey = az functionapp keys list --subscription $subscriptionId -g $resourceGroupName -n $functionAppName --query 'systemKeys.connector_extension' -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($connectorExtensionKey) -or $connectorExtensionKey -eq 'null') {
    throw 'Failed to fetch the connector_extension system key.'
}

$functionName = 'OnAzureBlobUpdatedFile'
$operationName = 'OnUpdatedFiles_V2'
$triggerName = "$connectorNamespaceConnectionName-$($functionName.ToLowerInvariant())"
$callbackUrl = "https://$($outputs.functionAppDefaultHostname)/runtime/webhooks/connector?functionName=$functionName"
$notifFile = Join-Path ([IO.Path]::GetTempPath()) "blob-notification-$([guid]::NewGuid()).json"
$parametersFile = Join-Path ([IO.Path]::GetTempPath()) "blob-parameters-$([guid]::NewGuid()).json"
$connectionFile = Join-Path ([IO.Path]::GetTempPath()) "blob-connection-$([guid]::NewGuid()).json"
$metadataFile = Join-Path ([IO.Path]::GetTempPath()) "blob-metadata-$([guid]::NewGuid()).json"
$ownedFiles = [Collections.Generic.List[string]]::new()
$failure = $null
try {
    $notification = @{
        callbackUrl = $callbackUrl
        authentication = @{
            type = 'QueryString'
            name = 'code'
            value = $connectorExtensionKey
        }
    }
    foreach ($document in @(
        @{ path = $notifFile; value = $notification },
        @{ path = $parametersFile; value = @(@{ name = 'dataset'; value = $monitoredStorageAccountName }, @{ name = 'folderId'; value = $folderId }) },
        @{ path = $connectionFile; value = @{ connectionName = $connectorNamespaceConnectionName; connectorName = 'azureblob' } },
        @{ path = $metadataFile; value = @{ destinationType = 'functionApp'; functionAppName = $functionAppName; functionAppResourceGroup = $resourceGroupName; functionAppSubscriptionId = $subscriptionId; functionName = $functionName; recurrenceFrequency = 'Minute'; recurrenceInterval = '5' } }
    )) {
        $stream = New-PrivateStagingStream $document.path
        $ownedFiles.Add($document.path)
        try {
            $bytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $document.value -Depth 5 -Compress))
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush($true)
        } finally { $stream.Dispose() }
    }
    $verb = if ($triggerName -in $existingTriggers) { 'update' } else { 'create' }
    az connector-namespace trigger $verb `
        --subscription $subscriptionId -g $resourceGroupName --namespace $connectorNamespaceName `
        -n $triggerName `
        --connection-details "@$connectionFile" `
        --operation-name $operationName `
        --parameters "@$parametersFile" `
        --notification-details "@$notifFile" `
        --state Enabled `
        --description 'When a blob is added or modified (properties only) (V2)' `
        --metadata "@$metadataFile" `
        -o none 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create trigger config for '$functionName'."
    }
} catch { $failure = $_; throw }
finally {
    $cleanupFailed = $false
    foreach ($path in $ownedFiles) {
        try { if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) } }
        catch { $cleanupFailed = $true; Write-Warning 'Could not clean owned callback staging file.' }
    }
    if ($cleanupFailed -and $null -eq $failure) { throw 'Callback staging cleanup failed.' }
}

Write-Host "Done. Upload blobs to '$containerName' in '$monitoredStorageAccountName' to fire the trigger." -ForegroundColor Green