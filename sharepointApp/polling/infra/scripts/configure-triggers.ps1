$ErrorActionPreference = 'Stop'
$python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
& $python (Join-Path $PSScriptRoot 'trigger_setup.py') @args
if ($LASTEXITCODE -ne 0) { throw 'Trigger setup failed.' }
