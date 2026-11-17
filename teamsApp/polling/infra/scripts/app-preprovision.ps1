$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'prepare-app.ps1')
$python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
& $python (Join-Path $PSScriptRoot 'detect_app.py')
if ($LASTEXITCODE -ne 0) { throw 'Failed to check the existing Function App.' }
