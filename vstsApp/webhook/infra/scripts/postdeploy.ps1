param([switch] $ForceLocalSettings)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$setup = Join-Path $PSScriptRoot '../../../scripts/setup.py'
$arguments = @($setup, '--mode', 'webhook', '--project', $project)
if ($ForceLocalSettings) { $arguments += '--force-local-settings' }
& python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Azure DevOps webhook setup failed. See the mode README.' }