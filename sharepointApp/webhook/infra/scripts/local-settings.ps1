function Invoke-SharepointSetup {
    param([string[]] $Options)
    $ErrorActionPreference = 'Stop'
    $pythonCommand = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
    & $pythonCommand (Join-Path $PSScriptRoot '../../../scripts/setup.py') --mode webhook --project (Join-Path $PSScriptRoot '../..') @Options
    if ($LASTEXITCODE -ne 0) { throw 'SharePoint setup failed.' }
}