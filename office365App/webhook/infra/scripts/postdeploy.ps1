param(
    [string] $CallbackBaseUrl,
    [string] $ConnectorExtensionKey,
    [switch] $ForceLocalSettings,
    [switch] $ConsentLinkOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
$setupArguments = @()
if ($ForceLocalSettings) { $setupArguments += '--force-local-settings' }
if ($ConsentLinkOnly) { $setupArguments += '--consent-link-only' }
if ($CallbackBaseUrl) { $setupArguments += @('--callback-base-url', $CallbackBaseUrl) }
if ($ConnectorExtensionKey) { $setupArguments += @('--connector-extension-key', $ConnectorExtensionKey) }
Invoke-Office365Setup -SetupArguments $setupArguments
