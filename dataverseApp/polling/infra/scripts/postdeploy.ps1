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
) + @(Get-DataverseSeparateRowTriggers)
foreach ($functionName in @('OnDataverseRowChanged') + @($optional.functionName)) {
    $name = "${functionName}TriggerConfigName"
    if ([string]$settings.$name -cne "dataverse-$($functionName.ToLowerInvariant())") { throw "Missing or invalid $name in triggerConfigSettings." }
    $localValues[$name] = [string]$settings.$name
}
foreach ($trigger in $optional) {
    $name = "AzureWebJobs.$($trigger.functionName).Disabled"
    $disabled = ([string]$settings.$name).ToLowerInvariant()
    if ($disabled -cnotin @('true', 'false')) { throw "Missing or invalid $name in triggerConfigSettings." }
    $localValues[$name] = $disabled
}
$actionSelectors = [ordered]@{ organization = $context.organization }
if ($localValues['AzureWebJobs.OnDataverseActionPerformed.Disabled'] -ceq 'false') {
    foreach ($pair in @(@('catalog', 'eventCatalog'), @('category', 'eventCategory'),
        @('entityname', 'eventTable'), @('sdkmessagename', 'eventAction'))) {
        $value = [string]$outputs.($pair[1])
        if ([string]::IsNullOrWhiteSpace($value)) { throw "Missing action selector $($pair[1])." }
        $actionSelectors[$pair[0]] = $value
    }
}
$rowParameters = if (@(Get-DataverseSeparateRowTriggers | Where-Object {
    $localValues["AzureWebJobs.$($_.functionName).Disabled"] -ceq 'false'
}).Count -gt 0) { @(Get-DataverseRowParameters $outputs) }
$configurationsToCreate = @()
$inventory = @(Get-DataverseConfigurations $collectionUri)
foreach ($trigger in Get-DataverseSeparateRowTriggers) {
    $name = $localValues["$($trigger.functionName)TriggerConfigName"]
    $existing = @($inventory | Where-Object { $_.config.name -ieq $name -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$name" })
    if ($existing.Count -gt 1) { throw "Ambiguous Dataverse configuration '$name'." }
    if ($existing.Count -eq 1) { Assert-DataverseRowConfig $existing[0].config $trigger $outputs Poll }
}
foreach ($trigger in $optional) {
    $name = $localValues["$($trigger.functionName)TriggerConfigName"]
    $desiredState = if ($localValues["AzureWebJobs.$($trigger.functionName).Disabled"] -ceq 'true') { 'Disabled' } else { 'Enabled' }
    $existing = @($inventory | Where-Object { $_.config.name -ieq $name -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$name" })
    if ($existing.Count -gt 1) { throw "Ambiguous Dataverse configuration '$name'." }
    if ($existing.Count -eq 0) {
        if ($desiredState -ceq 'Enabled') {
            $parameters = if ($trigger.operationName -ceq 'BusinessEventsTrigger') {
                Protect-DataverseActionRegistration $context $journal $null $outputs -BeforeCreate
                @($actionSelectors.Keys | ForEach-Object { @{ name = $_; value = $actionSelectors[$_] } })
            } else { $rowParameters }
            $configurationsToCreate += @{
                name = $name; functionName = $trigger.functionName
                operationName = $trigger.operationName; parameters = $parameters
            }
        }
        continue
    }
    $config = $existing[0].config
    if ($config.name -cne $name) { throw 'Dataverse configuration name differs.' }
    Assert-DataverseDestination $context $config $outputs $trigger.operationName $trigger.functionName
    if ($trigger.operationName -ceq 'BusinessEventsTrigger') {
        Protect-DataverseActionRegistration $context $journal $config $outputs -BeforeCreate:($desiredState -ceq 'Enabled')
        if ($desiredState -ceq 'Enabled') {
            $currentSelectors = @{}
            foreach ($parameter in $config.properties.parameters) { $currentSelectors[$parameter.name] = [string]$parameter.value }
            Assert-DataverseActionContext $actionSelectors $currentSelectors
        }
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
        $options = [System.Text.Json.JsonDocumentOptions]::new()
        $options.MaxDepth = 100
        $body.Add('properties', [System.Text.Json.Nodes.JsonNode]::Parse($node['properties'].ToJsonString($serializer), $null, $options))
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
foreach ($registration in $configurationsToCreate) {
    $name = $registration.name
    $body = @{ properties = @{
        connectionDetails = @{ connectionName = $context.connectionName; connectorName = 'commondataservice' }
        deliveryMode = 'Poll'; operationName = $registration.operationName; parameters = $registration.parameters
        state = 'Enabled'; type = 'NotSpecified'
        description = 'Portal Dataverse subscription operation with Poll delivery.'
        metadata = @{ destinationType = 'functionApp'; functionAppName = $outputs.functionAppName
            functionAppResourceGroup = $outputs.resourceGroupName; functionAppSubscriptionId = $outputs.AZURE_SUBSCRIPTION_ID
            functionName = $registration.functionName }
    } }
    $bodyFile = Join-Path ([IO.Path]::GetTempPath()) "dataverse-action-$([guid]::NewGuid().ToString('N')).json"
    $owned = $false; $failure = $null
    try {
        Write-PrivateJson $bodyFile ($body | ConvertTo-Json -Depth 10)
        $owned = $true
        az rest --method put --url "$collectionUri/${name}?api-version=2026-05-01-preview" --body "@$bodyFile" -o none 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Could not create guarded Dataverse configuration '$name'; source details were not logged." }
        $raw = az rest --method get --url "$collectionUri/${name}?api-version=2026-05-01-preview" `
            --query '{state:properties.state,deliveryMode:properties.deliveryMode}' -o json 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Could not verify Dataverse configuration '$name' after creation." }
        $created = ($raw -join "`n") | ConvertFrom-Json
        if ($created.state -cne 'Enabled' -or $created.deliveryMode -cne 'Poll') { throw 'Dataverse configuration state or Poll delivery readback differs.' }
    } catch { $failure = $_; throw } finally {
        try { if ($owned -and [IO.File]::Exists($bodyFile)) { [IO.File]::Delete($bodyFile) } } catch {
            if ($null -eq $failure) { throw 'Could not clean private Dataverse registration staging file.' }
            Write-Warning 'Could not clean private registration staging file; original failure preserved.'
        }
    }
}
$enabledNames = @($localValues.OnDataverseRowChangedTriggerConfigName)
foreach ($trigger in $optional) {
    if ($localValues["AzureWebJobs.$($trigger.functionName).Disabled"] -ceq 'false') {
        $enabledNames += $localValues["$($trigger.functionName)TriggerConfigName"]
    }
}
Test-DataverseSourceStatus $collectionUri $enabledNames