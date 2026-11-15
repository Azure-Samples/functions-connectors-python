#requires -Version 7.3
param([switch] $ForceLocalSettings)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'deployment-helpers.ps1')
. (Join-Path $PSScriptRoot 'row-config.ps1')
Get-Command az, azd -ErrorAction Stop | Out-Null
$extension = az extension show --name connector-namespace --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extension) { throw 'Install the connector-namespace Azure CLI extension before running this script.' }
$raw = azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read the selected azd environment.' }
$outputs = ($raw -join "`n") | ConvertFrom-Json
foreach ($name in @('enableActionTrigger', 'enableSeparateRowTriggers')) {
    if ([string]$outputs.$name -cnotin @('true', 'false')) { throw "Missing or invalid azd output $name. Run azd provision first." }
}
$actionEnabled = [string]$outputs.enableActionTrigger -ceq 'true'
$separateEnabled = [string]$outputs.enableSeparateRowTriggers -ceq 'true'
if ([string]::IsNullOrWhiteSpace([string]$outputs.dataverseTableName)) { throw 'Missing Dataverse table selector.' }
$rowParameters = if ($separateEnabled) { @(Get-DataverseRowParameters $outputs) }
if ($actionEnabled) {
    foreach ($name in @('eventCatalog', 'eventCategory', 'eventTable', 'eventAction')) {
        if ([string]::IsNullOrWhiteSpace([string]$outputs.$name)) { throw "Missing business-event value $name." }
    }
}
$context = Get-DataverseActionContext $outputs Webhook
$journal = Get-DataverseActionJournal (Join-Path $PSScriptRoot '../..') $context
$collectionUri = "https://management.azure.com$($context.namespaceId)/triggerConfigs"
$localValues = @{
    AzureWebJobsStorage = 'UseDevelopmentStorage=true'
    FUNCTIONS_WORKER_RUNTIME = 'python'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'
}
$optional = @(
    @{ functionName = 'OnDataverseActionPerformed'; operationName = 'BusinessEventsTrigger'; enabled = $actionEnabled }
    foreach ($trigger in Get-DataverseSeparateRowTriggers) {
        $trigger.enabled = $separateEnabled
        $trigger
    }
)
foreach ($trigger in $optional) { $localValues["AzureWebJobs.$($trigger.functionName).Disabled"] = (-not $trigger.enabled).ToString().ToLowerInvariant() }
$inventory = @(Get-DataverseConfigurations $collectionUri)
foreach ($trigger in Get-DataverseSeparateRowTriggers) {
    $name = "$($outputs.connectorNamespaceConnectionName)-$($trigger.functionName.ToLowerInvariant())"
    $existing = @($inventory | Where-Object { $_.config.name -ieq $name -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$name" })
    if ($existing.Count -gt 1) { throw "Ambiguous Dataverse configuration '$name'." }
    if ($existing.Count -eq 1) {
        Assert-DataverseRowConfig $existing[0].config $trigger $outputs Webhook
        if ($separateEnabled -and $existing[0].config.properties.state -cne 'Enabled') {
            throw "Existing Dataverse row configuration '$name' is not Enabled; inspect it before changing its source registration."
        }
    }
}
Write-LocalSettings $localValues -Force:$ForceLocalSettings
foreach ($trigger in $optional) {
    $name = "$($outputs.connectorNamespaceConnectionName)-$($trigger.functionName.ToLowerInvariant())"
    $existing = @($inventory | Where-Object { $_.config.name -ieq $name -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$name" })
    if ($existing.Count -gt 1) { throw "Ambiguous Dataverse configuration '$name'." }
    $config = if ($existing.Count -eq 1) { $existing[0].config } else { $null }
    if ($null -ne $config) {
        if ($config.name -cne $name) { throw 'Dataverse configuration name differs.' }
        Assert-DataverseDestination $context $config $outputs $trigger.operationName $trigger.functionName
    }
    if ($trigger.operationName -ceq 'BusinessEventsTrigger' -and -not $trigger.enabled) {
        Protect-DataverseActionRegistration $context $journal $config $outputs
    }
    if ($null -ne $config -and -not $trigger.enabled) {
        az rest --method delete --url "$collectionUri/${name}?api-version=2026-05-01-preview" -o none 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Could not remove disabled Dataverse subscription '$name'." }
        Write-Host "Removed Connector Namespace configuration '$name'; source cleanup is not verified."
    }
}
Connect-Dataverse $outputs
$key = az functionapp keys list -g $outputs.resourceGroupName -n $outputs.functionAppName --query systemKeys.connector_extension -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$key) -or $key -eq 'null') { throw 'Connector extension system key unavailable.' }
$hostname = az resource show -g $outputs.resourceGroupName -n $outputs.functionAppName --resource-type Microsoft.Web/sites --query properties.defaultHostName -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$hostname) -or $hostname -eq 'null') { throw 'Function hostname unavailable.' }
if ($outputs.functionAppDefaultHostname -and $outputs.functionAppDefaultHostname -ine $hostname) { throw 'Function hostname differs from deployment outputs.' }
$organization = $context.organization
$triggers = @(@{
    functionName = 'OnDataverseRowChanged'; operationName = 'SubscribeWebhookTrigger'
    parameters = @(@{ name = 'organization'; value = $organization }, @{ name = 'entityname'; value = $outputs.dataverseTableName },
        @{ name = 'message'; value = '7' }, @{ name = 'scope'; value = '4' })
})
if ($actionEnabled) {
    $triggers += @{
        functionName = 'OnDataverseActionPerformed'; operationName = 'BusinessEventsTrigger'
        parameters = @(@{ name = 'organization'; value = $organization }, @{ name = 'catalog'; value = $outputs.eventCatalog },
            @{ name = 'category'; value = $outputs.eventCategory }, @{ name = 'entityname'; value = $outputs.eventTable },
            @{ name = 'sdkmessagename'; value = $outputs.eventAction })
    }
}
if ($separateEnabled) {
    foreach ($trigger in $optional | Where-Object operationName -NE 'BusinessEventsTrigger') {
        $triggers += @{
            functionName = $trigger.functionName; operationName = $trigger.operationName
            parameters = $rowParameters
        }
    }
}
$registeredNames = @()
foreach ($trigger in $triggers) {
    $name = "$($outputs.connectorNamespaceConnectionName)-$($trigger.functionName.ToLowerInvariant())"
    $registeredNames += $name
    $existing = @($inventory | Where-Object { $_.config.name -ieq $name -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$name" })
    if ($existing.Count -gt 1) { throw "Ambiguous Dataverse configuration '$name'." }
    $config = if ($existing.Count -eq 1) { $existing[0].config } else { $null }
    if ($null -ne $config) { Assert-DataverseDestination $context $config $outputs $trigger.operationName $trigger.functionName }
    if ($null -ne $config -and $trigger.operationName -cin @((Get-DataverseSeparateRowTriggers).operationName)) {
        Write-Host "Preserved existing Dataverse row configuration '$name'; no new source registration requested."
        continue
    }
    if ($trigger.operationName -ceq 'BusinessEventsTrigger') {
        Protect-DataverseActionRegistration $context $journal $config $outputs -BeforeCreate
        if ($null -ne $config) {
            if ($config.properties.state -cne 'Enabled') { throw 'Existing Dataverse action configuration is not Enabled; it was not recreated.' }
            $expected = @{}; $current = @{}
            foreach ($parameter in $trigger.parameters) { $expected[$parameter.name] = [string]$parameter.value }
            foreach ($parameter in $config.properties.parameters) { $current[$parameter.name] = [string]$parameter.value }
            Assert-DataverseActionContext $expected $current
            Write-Host "Preserved existing Dataverse action configuration '$name'; no new source registration requested."
            continue
        }
    }
    $bodyFile = Join-Path ([IO.Path]::GetTempPath()) "dataverse-notification-$([guid]::NewGuid().ToString('N')).json"
    $body = @{ properties = @{
        connectionDetails = @{ connectionName = $outputs.connectorNamespaceConnectionName; connectorName = 'commondataservice' }
        operationName = $trigger.operationName; parameters = $trigger.parameters; state = 'Enabled'; type = 'NotSpecified'
        metadata = @{ destinationType = 'functionApp'; functionAppName = $outputs.functionAppName
            functionAppResourceGroup = $outputs.resourceGroupName; functionAppSubscriptionId = $outputs.AZURE_SUBSCRIPTION_ID; functionName = $trigger.functionName }
        notificationDetails = @{ callbackUrl = "https://$hostname/runtime/webhooks/connector?functionName=$($trigger.functionName)"
            authentication = @{ type = 'QueryString'; name = 'code'; value = $key } }
    } }
    $owned = $false; $failure = $null
    try {
        Write-PrivateJson $bodyFile ($body | ConvertTo-Json -Depth 10)
        $owned = $true
        az rest --method put --url "$collectionUri/${name}?api-version=2026-05-01-preview" --body "@$bodyFile" -o none 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Could not configure Dataverse trigger '$name'; callback credentials were not logged." }
    } catch { $failure = $_; throw } finally {
        try { if ($owned -and [IO.File]::Exists($bodyFile)) { [IO.File]::Delete($bodyFile) } } catch {
            if ($null -eq $failure) { throw 'Could not clean owned callback staging file.' }
            Write-Warning 'Could not clean owned callback staging file; original failure preserved.'
        }
    }
}
$key = $null; $body = $null
Test-DataverseSourceStatus $collectionUri $registeredNames
if (-not $actionEnabled) { Assert-DataverseActionSourceCleanup $journal }
Write-Host 'Dataverse webhook configuration setup complete. Check the reported source status before testing events.'
