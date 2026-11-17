param([switch] $ForceLocalSettings)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
$options = @('--local-settings-only')
if ($ForceLocalSettings) { $options += '--force-local-settings' }
Invoke-SharepointSetup -Options $options