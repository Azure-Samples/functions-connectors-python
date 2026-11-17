param([string] $InputsFile)
$ErrorActionPreference = 'Stop'
$arguments = @((Join-Path $PSScriptRoot 'setup.py'), '--mode', 'polling', '--phase', 'sources')
if ($InputsFile) { $arguments += @('--inputs', $InputsFile) }
& python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Planner polling source setup failed.' }