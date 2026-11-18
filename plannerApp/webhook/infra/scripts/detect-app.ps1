$ErrorActionPreference = 'Stop'
$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
& $python (Join-Path $PSScriptRoot 'setup.py') --mode webhook --phase detect
if ($LASTEXITCODE -ne 0) { throw 'Failed to check the existing Planner Function App.' }