#requires -Version 7.3
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'deployment-helpers.ps1')
. (Join-Path $PSScriptRoot 'row-config.ps1')
. (Join-Path $PSScriptRoot 'selectors.ps1')
Get-Command az, azd -ErrorAction Stop | Out-Null
$extension = az extension show --name connector-namespace --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extension) { throw 'The connector-namespace Azure CLI extension is required.' }
$raw = azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read the selected azd environment.' }
$outputs = ($raw -join "`n") | ConvertFrom-Json
$context = Get-DataverseActionContext $outputs Poll
Connect-Dataverse $outputs
Resolve-DataverseSelectors $outputs

$inventory = @(Get-DataverseConfigurations "https://management.azure.com$($context.namespaceId)/triggerConfigs")
$combinedName = 'dataverse-ondataverserowchanged'
$combined = @($inventory | Where-Object {
    $_.config.name -ieq $combinedName -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$combinedName"
})
if ($combined.Count -gt 1) { throw "Ambiguous Dataverse configuration '$combinedName'." }
if ($combined.Count -eq 1) {
    if ($combined[0].config.name -cne $combinedName) { throw 'Dataverse configuration name differs.' }
    Assert-DataverseDestination $context $combined[0].config $outputs 'SubscribeWebhookTrigger' 'OnDataverseRowChanged'
    Assert-DataverseCombinedRowConfig $combined[0].config $outputs
}
foreach ($trigger in Get-DataverseSeparateRowTriggers) {
    $name = "dataverse-$($trigger.functionName.ToLowerInvariant())"
    $existing = @($inventory | Where-Object {
        $_.config.name -ieq $name -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$name"
    })
    if ($existing.Count -gt 1) { throw "Ambiguous Dataverse configuration '$name'." }
    if ($existing.Count -eq 1) { Assert-DataverseRowConfig $existing[0].config $trigger $outputs Poll }
}
$actionName = $context.triggerName
$action = @($inventory | Where-Object {
    $_.config.name -ieq $actionName -or $_.config.id -ieq "$($context.namespaceId)/triggerConfigs/$actionName"
})
if ($action.Count -gt 1) { throw "Ambiguous Dataverse configuration '$actionName'." }
$journal = Get-DataverseActionJournal (Join-Path $PSScriptRoot '../..') $context
if ($action.Count -eq 1) {
    $config = $action[0].config
    Assert-DataverseDestination $context $config $outputs 'BusinessEventsTrigger' 'OnDataverseActionPerformed'
    $expected = [ordered]@{
        organization = $context.organization
        catalog = [string]$outputs.eventCatalog
        category = [string]$outputs.eventCategory
        entityname = [string]$outputs.eventTable
        sdkmessagename = [string]$outputs.eventAction
    }
    $actual = @{}
    foreach ($parameter in $config.properties.parameters) {
        if ($actual.ContainsKey($parameter.name)) { throw 'Ambiguous Dataverse action selectors.' }
        $actual[$parameter.name] = [string]$parameter.value
    }
    Assert-DataverseActionContext $expected $actual
    Protect-DataverseActionRegistration $context $journal $config $outputs -BeforeCreate
} elseif (Test-Path -LiteralPath $journal) {
    Protect-DataverseActionRegistration $context $journal $null $outputs -BeforeCreate
}
