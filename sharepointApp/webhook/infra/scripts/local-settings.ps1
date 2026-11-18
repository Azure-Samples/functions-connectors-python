function Invoke-SharepointSetup {
    param([string[]] $Options)
    $ErrorActionPreference = 'Stop'
    $pythonCommand = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
    & $pythonCommand (Join-Path $PSScriptRoot 'setup.py') --mode webhook --project (Join-Path $PSScriptRoot '../..') @Options
    if ($LASTEXITCODE -ne 0) { throw 'SharePoint setup failed.' }
}