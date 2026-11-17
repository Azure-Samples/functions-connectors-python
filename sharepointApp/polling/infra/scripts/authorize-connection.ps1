$ErrorActionPreference = 'Stop'
$python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
& $python (Join-Path $PSScriptRoot 'select_sources.py')
if ($LASTEXITCODE -ne 0) { throw 'SharePoint authorization or source selection failed.' }
