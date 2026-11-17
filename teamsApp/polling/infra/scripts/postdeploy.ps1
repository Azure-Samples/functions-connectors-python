param([switch] $ForceLocalSettings)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'prepare-app.ps1') -LocalSettingsOnly -ForceLocalSettings:$ForceLocalSettings
