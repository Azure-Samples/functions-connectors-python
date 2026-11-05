#requires -Version 7.3
function New-PrivateStagingStream {
    param([string] $Path)
    $options = [IO.FileStreamOptions]::new()
    $options.Mode = [IO.FileMode]::CreateNew
    $options.Access = [IO.FileAccess]::Write
    $options.Share = [IO.FileShare]::None
    if (-not $IsWindows) { $options.UnixCreateMode = [IO.UnixFileMode]::UserRead -bor [IO.UnixFileMode]::UserWrite }
    return [IO.File]::Open($Path, $options)
}

function Write-PrivateJson {
    param([string] $Path, [string] $Json, [switch] $Replace)
    $temporary = "$Path.$([Guid]::NewGuid().ToString('N')).tmp"
    $owned = $false
    $failure = $null
    try {
        $stream = New-PrivateStagingStream $temporary
        $owned = $true
        try {
            $stream.Write([Text.UTF8Encoding]::new($false).GetBytes($Json))
            $stream.Flush($true)
        } finally { $stream.Dispose() }
        Get-Content -LiteralPath $temporary -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable | Out-Null
        [IO.File]::Move($temporary, $Path, [bool]$Replace)
    } catch { $failure = $_; throw } finally {
        try {
            if ($owned -and [IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        } catch {
            if ($null -eq $failure) { throw 'Could not clean private JSON staging file.' }
            Write-Warning 'Could not clean private JSON staging file; original failure preserved.'
        }
    }
}

function Write-LocalSettings {
    param([hashtable] $Values, [switch] $Force)
    $path = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../local.settings.json'))
    if (Test-Path -LiteralPath $path) {
        $item = Get-Item -LiteralPath $path -Force
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'local.settings.json must be a regular file, not a directory or link.'
        }
        if (-not $Force) {
            Write-Host 'Existing local.settings.json preserved byte-for-byte. Use -ForceLocalSettings to regenerate it.'
            return
        }
    }
    Write-PrivateJson $path (@{ IsEncrypted = $false; Values = $Values } | ConvertTo-Json -Depth 5) -Replace:$Force
    Write-Host 'Created ignored local.settings.json using developer credentials and Azurite.'
}