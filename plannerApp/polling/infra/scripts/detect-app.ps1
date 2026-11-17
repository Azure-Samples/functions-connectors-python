$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'setup.py') --mode polling --phase detect
if ($LASTEXITCODE -ne 0) { throw 'Failed to check the existing Planner Function App.' }