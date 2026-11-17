$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
& python (Join-Path $PSScriptRoot 'setup.py') --mode polling --project $project --phase prepare-app
if ($LASTEXITCODE -ne 0) { throw 'Could not detect the existing Function App; settings preservation requires a successful inventory read.' }