param([switch] $ForceLocalSettings, [string] $Inputs)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
$setupArguments = @()
if ($ForceLocalSettings) { $setupArguments += '--force' }
if ($Inputs) { $setupArguments += @('--inputs', $Inputs) }
Invoke-SalesforceSetup -SetupArguments $setupArguments