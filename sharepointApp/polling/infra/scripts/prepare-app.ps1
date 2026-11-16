$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
Invoke-SharepointSetup -Options @('--prepare-app')
