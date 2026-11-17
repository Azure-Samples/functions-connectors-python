$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
Invoke-SalesforceSetup -SetupArguments @('--phase', 'triggers')