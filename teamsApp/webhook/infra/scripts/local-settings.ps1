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

function Test-LocalSettingsFile {
    param([string] $Path)
    try { $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop }
    catch [System.Management.Automation.ItemNotFoundException] { return $false }
    if ($item -isnot [IO.FileInfo] -or $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'local.settings.json must be a regular file, not a directory or link.'
    }
    return $true
}

function Write-LocalSettings {
    param([hashtable] $Values, [switch] $Force)
    $path = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../local.settings.json'))
    if ((Test-LocalSettingsFile $path) -and -not $Force) {
        Write-Host 'Existing local.settings.json preserved byte-for-byte.'
        return
    }
    $json = @{ IsEncrypted = $false; Values = $Values } | ConvertTo-Json -Depth 5
    $temp = Join-Path ([IO.Path]::GetDirectoryName($path)) ".local-settings-$([guid]::NewGuid().ToString('N')).tmp"
    $failure = $null
    $tempOwned = $false
    try {
        $stream = New-PrivateStagingStream $temp
        $tempOwned = $true
        $streamFailure = $null
        try {
            $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json)
            $stream.Write($bytes)
            $stream.Flush($true)
        } catch { $streamFailure = $_; throw }
        finally {
            try { $stream.Dispose() }
            catch {
                if ($null -eq $streamFailure) { throw 'Could not close owned local-settings staging stream.' }
                Write-Warning 'Could not close owned staging stream; original failure preserved.'
            }
        }
        if ($Force) { Test-LocalSettingsFile $path | Out-Null }
        [IO.File]::Move($temp, $path, [bool]$Force)
        Write-Host 'Created ignored local.settings.json for developer authentication and Azurite.'
    } catch { $failure = $_; throw }
    finally {
        try {
            if ($tempOwned -and [IO.File]::Exists($temp)) { [IO.File]::Delete($temp) }
        } catch {
            if ($null -eq $failure) { throw 'Could not clean owned local-settings staging file.' }
            Write-Warning 'Could not clean owned local-settings staging file; original failure preserved.'
        }
    }
}