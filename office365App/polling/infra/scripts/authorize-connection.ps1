$ErrorActionPreference = 'Stop'
$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
& $python (Join-Path $PSScriptRoot 'select_sources.py')
if ($LASTEXITCODE -ne 0) { throw 'Office 365 authorization or source selection failed.' }
