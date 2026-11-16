$ErrorActionPreference = 'Stop'
Get-Command azd -ErrorAction Stop | Out-Null
$raw = azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Could not read the selected azd environment.' }
$values = ($raw -join "`n") | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$values.DATAVERSE_ENVIRONMENT_URL)) {
    throw 'DATAVERSE_ENVIRONMENT_URL is required. Set the Dataverse organization URL, not its friendly name.'
}
$organization = $null
if (-not [Uri]::TryCreate([string]$values.DATAVERSE_ENVIRONMENT_URL, [UriKind]::Absolute, [ref]$organization) -or
    $organization.Scheme -ne 'https' -or -not $organization.Host -or $organization.UserInfo -or
    $organization.AbsolutePath.Trim('/') -or $organization.Query -or $organization.Fragment) {
    throw 'DATAVERSE_ENVIRONMENT_URL must be an HTTPS organization URL without credentials, a path, query, or fragment.'
}