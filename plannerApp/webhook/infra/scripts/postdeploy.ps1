param([string] $InputsFile, [switch] $Force)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$helper = (Resolve-Path (Join-Path $PSScriptRoot '../../../scripts/setup.py')).Path
$arguments = @($helper, '--mode', 'webhook', '--project', $project)
if ($InputsFile) { $arguments += @('--inputs', $InputsFile) }
if ($Force) { $arguments += '--force' }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python is required.' }
& python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Planner webhook setup failed.' }