function Invoke-SalesforceSetup {
    param([string[]] $SetupArguments)
    $helper = Join-Path $PSScriptRoot '../../../scripts/setup.py'
    $project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    $python = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
    & $python $helper --mode polling --project $project @SetupArguments
    if ($LASTEXITCODE -ne 0) { throw 'Salesforce polling setup failed.' }
}