param([switch] $ForceLocalSettings)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$setup = Join-Path $PSScriptRoot 'setup.py'
$arguments = @($setup, '--mode', 'webhook', '--project', $project)
if ($ForceLocalSettings) { $arguments += '--force-local-settings' }
$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Azure DevOps webhook setup failed. See the mode README.' }