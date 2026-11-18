#requires -Version 7.3
param([Parameter(Mandatory)] [string] $RequestPath)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'deployment-helpers.ps1')
$request = Get-Content -LiteralPath $RequestPath -Raw | ConvertFrom-Json -Depth 100
$outputs = $request.outputs
$selectors = Get-DataverseActionSelectors $request.parameters
$outputs.dataverseEnvironmentUrl = $selectors.organization
foreach ($pair in @(@('catalog', 'eventCatalog'), @('category', 'eventCategory'),
    @('entityname', 'eventTable'), @('sdkmessagename', 'eventAction'))) {
    $outputs | Add-Member -NotePropertyName $pair[1] -NotePropertyValue $selectors[$pair[0]] -Force
}
$context = Get-DataverseActionContext $outputs $request.mode
$journal = Get-DataverseActionJournal (Join-Path $PSScriptRoot '../..') $context
Protect-DataverseActionRegistration $context $journal $request.resource $outputs -BeforeCreate
