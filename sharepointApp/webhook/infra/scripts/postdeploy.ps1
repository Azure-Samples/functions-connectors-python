param(
    [switch] $ForceLocalSettings,
    [switch] $ConsentLinkOnly,
    [switch] $LocalSettingsOnly,
    [string] $CallbackBaseUrl,
    [string] $ConnectorExtensionKey
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
$options = @()
if ($ForceLocalSettings) { $options += '--force-local-settings' }
if ($ConsentLinkOnly) { $options += '--consent-link-only' }
if ($LocalSettingsOnly) { $options += '--local-settings-only' }
if ($CallbackBaseUrl) { $options += @('--callback-base-url', $CallbackBaseUrl) }
if ($ConnectorExtensionKey) { $options += @('--connector-extension-key', $ConnectorExtensionKey) }
Invoke-SharepointSetup -Options $options
