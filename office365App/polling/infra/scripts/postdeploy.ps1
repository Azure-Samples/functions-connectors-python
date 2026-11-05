param(
    [switch] $ForceLocalSettings,
    [switch] $ConsentLinkOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
$setupArguments = @()
if ($ForceLocalSettings) { $setupArguments += '--force-local-settings' }
if ($ConsentLinkOnly) { $setupArguments += '--consent-link-only' }
Invoke-Office365Setup -SetupArguments $setupArguments
