function Invoke-Office365Setup {
    param([string[]] $SetupArguments)
    $helper = Join-Path $PSScriptRoot 'setup.py'
    $project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    $python = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python3' }
    & $python $helper --mode webhook --project $project @SetupArguments
    if ($LASTEXITCODE -ne 0) { throw 'Office365 webhook setup failed.' }
}