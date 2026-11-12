$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
& python (Join-Path $PSScriptRoot '../../../scripts/setup.py') --mode polling --project $project --check-inputs
if ($LASTEXITCODE -ne 0) { throw 'Create polling/trigger-inputs.json from the reviewed example before provisioning.' }