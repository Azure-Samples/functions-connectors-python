function Invoke-SalesforceSetup {
    param([string[]] $SetupArguments)
    $helper = Join-Path $PSScriptRoot 'setup.py'
    $project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    $python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
    & $python $helper --mode polling --project $project @SetupArguments
    if ($LASTEXITCODE -ne 0) { throw 'Salesforce polling setup failed.' }
}