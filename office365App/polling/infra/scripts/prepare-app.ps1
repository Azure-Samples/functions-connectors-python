$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
Invoke-Office365Setup -SetupArguments @('--prepare-app')
