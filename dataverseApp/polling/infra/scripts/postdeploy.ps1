#requires -Version 7.3
param([switch] $ForceLocalSettings)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'deployment-helpers.ps1')
Get-Command az, azd -ErrorAction Stop | Out-Null
$extension = az extension show --name connector-namespace --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extension) { throw 'Install the connector-namespace Azure CLI extension before running this script.' }
$raw = azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read the selected azd environment.' }
$outputs = ($raw -join "`n") | ConvertFrom-Json
foreach ($name in @('connectorPollingEndpoint', 'triggerConfigSettings')) {
    if ([string]::IsNullOrWhiteSpace([string]$outputs.$name)) { throw "Missing azd output $name. Run azd provision first." }
}
$context = Get-DataverseActionContext $outputs Poll
$journal = Get-DataverseActionJournal (Join-Path $PSScriptRoot '../..') $context
$collectionUri = "https://management.azure.com$($context.namespaceId)/triggerConfigs"
$settings = if ($outputs.triggerConfigSettings -is [string]) { $outputs.triggerConfigSettings | ConvertFrom-Json } else { $outputs.triggerConfigSettings }
$localValues = @{
    AzureWebJobsStorage = 'UseDevelopmentStorage=true'
    FUNCTIONS_WORKER_RUNTIME = 'python'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'
    ConnectorNamespace__pollingEndpoint = $outputs.connectorPollingEndpoint
}
$optional = @(
    @{ functionName = 'OnDataverseActionPerformed'; operationName = 'BusinessEventsTrigger' }
    @{ functionName = 'OnDataverseRowAdded'; operationName = 'GetOnNewItems_V2' }
    @{ functionName = 'OnDataverseRowModified'; operationName = 'GetOnUpdatedItems_V2' }
    @{ functionName = 'OnDataverseRowDeleted'; operationName = 'GetOnDeletedItems_V2' }
)
foreach ($functionName in @('OnDataverseRowChanged') + @($optional.functionName)) {
    $name = "${functionName}TriggerConfigName"
    if ([string]$settings.$name -cne "dataverse-$($functionName.ToLowerInvariant())") { throw "Missing or invalid $name in triggerConfigSettings." }
    $localValues[$name] = [string]$settings.$name
}
foreach ($trigger in $optional) {
    $name = "AzureWebJobs.$($trigger.functionName).Disabled"
    if ([string]$settings.$name -cnotin @('true', 'false')) { throw "Missing or invalid $name in triggerConfigSettings." }
    $localValues[$name] = [string]$settings.$name
}
$inventory = @(Get-DataverseConfigurations $collectionUri)
foreach ($trigger in $optional) {
    $name = $localValues["$($trigger.functionName)TriggerConfigName"]
    $desiredState = if ($localValues["AzureWebJobs.$($trigger.functionName).Disabled"] -ceq 'true') { 'Disabled' } else { 'Enabled' }
    $existing = @($inventory | Where-Object { $_.config.name -ieq $name -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$name" })
    if ($existing.Count -gt 1) { throw "Ambiguous Dataverse configuration '$name'." }
    if ($existing.Count -eq 0) {
        if ($desiredState -eq 'Enabled') { throw "Selected Dataverse configuration '$name' is missing. Run azd provision first." }
        continue
    }
    $config = $existing[0].config
    if ($config.name -cne $name) { throw 'Dataverse configuration name differs.' }
    Assert-DataverseDestination $context $config $outputs $trigger.operationName $trigger.functionName
    if ($trigger.operationName -ceq 'BusinessEventsTrigger') {
        Protect-DataverseActionRegistration $context $journal $config $outputs
    } else {
        if ([string]::IsNullOrWhiteSpace([string]$outputs.dataverseEntitySetName)) { throw 'Missing dataverseEntitySetName output.' }
        $expected = @{ dataset = $context.organization; table = [string]$outputs.dataverseEntitySetName }
        $selectors = @{}
        foreach ($parameter in $config.properties.parameters) {
            if ($selectors.ContainsKey($parameter.name)) { throw 'Ambiguous Dataverse row selectors.' }
            $selectors[$parameter.name] = [string]$parameter.value
        }
        Assert-DataverseActionContext $expected $selectors
    }
    if ($config.properties.state -ceq $desiredState) { continue }
    $node = $existing[0].node
    $node['properties']['state'] = [System.Text.Json.Nodes.JsonValue]::Create($desiredState)
    $bodyFile = Join-Path ([IO.Path]::GetTempPath()) "dataverse-state-$([guid]::NewGuid().ToString('N')).json"
    $owned = $false
    $failure = $null
    try {
        $serializer = [System.Text.Json.JsonSerializerOptions]::new()
        $serializer.MaxDepth = 100
        $body = [System.Text.Json.Nodes.JsonObject]::new()
        $body.Add('properties', $node['properties'].DeepClone())
        [void]$body['properties'].Remove('provisioningState')
        [void]$body['properties'].Remove('pollingEndpoints')
        Write-PrivateJson $bodyFile ($body.ToJsonString($serializer))
        $owned = $true
        az rest --method put --url "$collectionUri/${name}?api-version=2026-05-01-preview" --body "@$bodyFile" -o none 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Could not update Dataverse configuration '$name'; source details were not logged." }
        $raw = az rest --method get --url "$collectionUri/${name}?api-version=2026-05-01-preview" `
            --query '{state:properties.state,deliveryMode:properties.deliveryMode}' -o json 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Could not verify Dataverse configuration '$name' after its state update." }
        $updated = ($raw -join "`n") | ConvertFrom-Json
        if ($updated.state -cne $desiredState -or $updated.deliveryMode -cne 'Poll') { throw 'Dataverse state or Poll delivery readback differs.' }
        Write-Host "Dataverse configuration '$name' is $desiredState; its namespace configuration was retained."
    } catch { $failure = $_; throw } finally {
        try { if ($owned -and [IO.File]::Exists($bodyFile)) { [IO.File]::Delete($bodyFile) } } catch {
            if ($null -eq $failure) { throw 'Could not clean private Dataverse state-update staging file.' }
            Write-Warning 'Could not clean private state-update staging file; original failure preserved.'
        }
    }
}
Write-LocalSettings $localValues -Force:$ForceLocalSettings
Connect-Dataverse $outputs
$enabledNames = @($localValues.OnDataverseRowChangedTriggerConfigName)
foreach ($trigger in $optional) {
    if ($localValues["AzureWebJobs.$($trigger.functionName).Disabled"] -ceq 'false') {
        $enabledNames += $localValues["$($trigger.functionName)TriggerConfigName"]
    }
}
Test-DataverseSourceStatus $collectionUri $enabledNames