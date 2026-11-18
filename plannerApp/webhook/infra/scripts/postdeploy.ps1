param([string] $InputsFile, [switch] $Force)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$helper = (Resolve-Path (Join-Path $PSScriptRoot 'setup.py')).Path
$arguments = @($helper, '--mode', 'webhook', '--project', $project)
if ($InputsFile) { $arguments += @('--inputs', $InputsFile) }
if ($Force) { $arguments += '--force' }
$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Planner webhook setup failed.' }