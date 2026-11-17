$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
& python (Join-Path $PSScriptRoot 'setup.py') --mode polling --project $project
if ($LASTEXITCODE -ne 0) { throw 'Polling consent, source selection or registration failed. App provisioning stopped.' }