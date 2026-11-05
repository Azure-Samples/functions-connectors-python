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
foreach ($name in @('DATAVERSE_ENABLE_ACTION_TRIGGER', 'DATAVERSE_ENABLE_SEPARATE_ROW_TRIGGERS')) {
    if ($values.PSObject.Properties.Name -contains $name -and [string]$values.$name -cnotin @('true', 'false')) {
        throw "$name must be true or false."
    }
}
if ($values.PSObject.Properties.Name -contains 'DATAVERSE_ENTITY_SET_NAME' -and
    [string]::IsNullOrWhiteSpace([string]$values.DATAVERSE_ENTITY_SET_NAME)) {
    throw 'DATAVERSE_ENTITY_SET_NAME must be a nonempty entity-set name (for example, accounts).'
}
if ([string]$values.DATAVERSE_ENABLE_ACTION_TRIGGER -ceq 'true') {
    foreach ($name in @('DATAVERSE_EVENT_CATALOG', 'DATAVERSE_EVENT_CATEGORY', 'DATAVERSE_EVENT_TABLE', 'DATAVERSE_EVENT_ACTION')) {
        if ([string]::IsNullOrWhiteSpace([string]$values.$name)) {
            throw "$name is required when DATAVERSE_ENABLE_ACTION_TRIGGER=true."
        }
    }
}