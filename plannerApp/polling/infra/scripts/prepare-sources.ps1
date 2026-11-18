param([string] $InputsFile)
$ErrorActionPreference = 'Stop'
$arguments = @((Join-Path $PSScriptRoot 'setup.py'), '--mode', 'polling', '--phase', 'sources')
if ($InputsFile) { $arguments += @('--inputs', $InputsFile) }
$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Planner polling source setup failed.' }