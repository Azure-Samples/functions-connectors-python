$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
& python (Join-Path $PSScriptRoot 'setup.py') --mode webhook --project $project --phase prepare-app
if ($LASTEXITCODE -ne 0) { throw 'Check the app inventory before provisioning. See the local README.' }