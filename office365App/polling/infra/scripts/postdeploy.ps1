param([switch] $ForceLocalSettings)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
$setupArguments = @('--local-settings-only')
if ($ForceLocalSettings) { $setupArguments += '--force-local-settings' }
Invoke-Office365Setup -SetupArguments $setupArguments
