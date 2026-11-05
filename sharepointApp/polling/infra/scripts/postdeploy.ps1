param([switch] $ForceLocalSettings, [switch] $ConsentLinkOnly, [switch] $LocalSettingsOnly)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
$options = @()
if ($ForceLocalSettings) { $options += '--force-local-settings' }
if ($ConsentLinkOnly) { $options += '--consent-link-only' }
if ($LocalSettingsOnly) { $options += '--local-settings-only' }
Invoke-SharepointSetup -Options $options