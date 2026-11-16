function Invoke-DataverseSelector {
    param($Outputs, [string] $Label, [string] $Method, [string] $Path, [hashtable] $Headers = @{})
    $request = @{ method = $Method; path = $Path }
    if ($Headers.Count) { $request.headers = $Headers }
    if ($Method -ceq 'POST') { $request.body = @{} }
    $requestFile = Join-Path ([IO.Path]::GetTempPath()) "dataverse-selector-$([guid]::NewGuid().ToString('N')).json"
    $owned = $false
    $failure = $null
    try {
        Write-PrivateJson $requestFile ($request | ConvertTo-Json -Depth 10)
        $owned = $true
        $raw = az connector-namespace connection invoke --subscription $Outputs.AZURE_SUBSCRIPTION_ID `
            -g $Outputs.resourceGroupName --namespace $Outputs.connectorNamespaceName `
            --connection-name $Outputs.connectorNamespaceConnectionName --request "@$requestFile" -o json 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Could not query Dataverse $Label choices." }
        $result = ($raw -join "`n") | ConvertFrom-Json -AsHashtable -Depth 100
        $status = 0
        $statusText = [string]$result.response.statusCode
        if (-not [int]::TryParse($statusText, [ref]$status) -and [Enum]::IsDefined([Net.HttpStatusCode], $statusText)) {
            $status = [int][Enum]::Parse([Net.HttpStatusCode], $statusText)
        }
        if ($status -lt 200 -or $status -ge 300) {
            throw "Could not query Dataverse $Label choices; check connection permissions and connector status."
        }
        $body = $result.response.body
        if ($body -is [array]) { return $body }
        if ($body -is [System.Collections.IDictionary] -and $body.value -is [array]) { return $body.value }
        throw "Unexpected response while querying Dataverse $Label choices."
    } catch { $failure = $_; throw } finally {
        try { if ($owned -and [IO.File]::Exists($requestFile)) { [IO.File]::Delete($requestFile) } } catch {
            if ($null -eq $failure) { throw 'Could not clean private Dataverse selector request.' }
            Write-Warning 'Could not clean private Dataverse selector request; original failure preserved.'
        }
    }
}

function Select-DataverseValue {
    param($Outputs, [string] $Property, [string] $Setting, [string] $Label,
        [object[]] $Options, [string] $ValueKey = '', [string] $TitleKey = '')
    if ([string]::IsNullOrWhiteSpace([string]$Outputs.$Property)) {
        if ($Options.Count -eq 0) {
            throw "No Dataverse $Label choices were returned. Configure an available source or set $Setting before rerunning."
        }
        $choices = @()
        foreach ($option in $Options) {
            if ($ValueKey -and $option -isnot [System.Collections.IDictionary]) {
                throw "Dataverse $Label choices contain an invalid item."
            }
            $valueFields = @()
            $titleFields = @()
            if ($ValueKey) { $valueFields = @($option.Keys | Where-Object { $_ -ieq $ValueKey }) }
            if ($TitleKey) { $titleFields = @($option.Keys | Where-Object { $_ -ieq $TitleKey }) }
            if (($ValueKey -and $valueFields.Count -ne 1) -or $titleFields.Count -gt 1) {
                throw "Dataverse $Label choices contain missing or ambiguous fields."
            }
            $value = if ($ValueKey) { [string]$option[$valueFields[0]] } else { [string]$option }
            $title = if ($titleFields.Count) { [string]$option[$titleFields[0]] } else { $value }
            if ([string]::IsNullOrWhiteSpace($value)) { throw "Dataverse $Label choices contain an invalid value." }
            if ([string]::IsNullOrWhiteSpace($title)) { $title = $value }
            $choices += @{ value = $value; title = $title }
        }
        $filtered = $choices
        do {
            $shown = @($filtered | Select-Object -First 25)
            Write-Host "Dataverse $Label choices (showing $($shown.Count) of $($filtered.Count)):"
            for ($i = 0; $i -lt $shown.Count; $i++) {
                Write-Host "[$($i + 1)] $($shown[$i].title) ($($shown[$i].value))"
            }
            $answer = Read-Host "Select $Label by number, enter text to filter, or * to show all"
            if ([string]::IsNullOrWhiteSpace($answer)) { throw "A Dataverse $Label selection is required; set $Setting to run without a prompt." }
            $index = 0
            $isNumber = [int]::TryParse($answer, [ref]$index)
            $valid = $isNumber -and $index -ge 1 -and $index -le $shown.Count
            if ($isNumber -and -not $valid) {
                Write-Host "Enter a number from 1 to $($shown.Count)."
            } elseif (-not $isNumber) {
                $matches = if ($answer -ceq '*') { $choices } else {
                    @($choices | Where-Object {
                        $_.title.IndexOf($answer, [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
                        $_.value.IndexOf($answer, [StringComparison]::OrdinalIgnoreCase) -ge 0
                    })
                }
                if (@($matches).Count -eq 0) { Write-Host 'No matching choices.' } else { $filtered = @($matches) }
            }
        } while (-not $valid)
        $value = $shown[$index - 1].value
        azd env set $Setting $value | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not save $Setting in the selected azd environment." }
        $Outputs.$Property = $value
    }
}

function Resolve-DataverseSelectors {
    param($Outputs)
    foreach ($pair in @(
        @('dataverseEntitySetName', 'DATAVERSE_ENTITY_SET_NAME'), @('dataverseRowScope', 'DATAVERSE_ROW_SCOPE'),
        @('eventCatalog', 'DATAVERSE_EVENT_CATALOG'), @('eventCategory', 'DATAVERSE_EVENT_CATEGORY'),
        @('eventTable', 'DATAVERSE_EVENT_TABLE'), @('eventAction', 'DATAVERSE_EVENT_ACTION')
    )) {
        if (-not [string]::IsNullOrWhiteSpace([string]$Outputs.($pair[1]))) {
            $Outputs.($pair[0]) = [string]$Outputs.($pair[1])
        }
    }
    $organization = [string]$Outputs.dataverseEnvironmentUrl
    $dataset = [uri]::EscapeDataString([uri]::EscapeDataString($organization.TrimEnd('/')))
    if ([string]::IsNullOrWhiteSpace([string]$Outputs.dataverseEntitySetName)) {
        $options = @(Invoke-DataverseSelector $Outputs 'table' GET "/datasets/$dataset/tables")
        Select-DataverseValue $Outputs dataverseEntitySetName DATAVERSE_ENTITY_SET_NAME 'table' $options Name DisplayName
    }
    if ([string]::IsNullOrWhiteSpace([string]$Outputs.dataverseRowScope)) {
        $table = [uri]::EscapeDataString([uri]::EscapeDataString([string]$Outputs.dataverseEntitySetName))
        $options = @(Invoke-DataverseSelector $Outputs 'scope' GET "/datasets/$dataset/tables/$table/scopefilters")
        Select-DataverseValue $Outputs dataverseRowScope DATAVERSE_ROW_SCOPE 'scope' $options
    }
    $headers = @{ organization = $organization }
    if ([string]::IsNullOrWhiteSpace([string]$Outputs.eventCatalog)) {
        $options = @(Invoke-DataverseSelector $Outputs 'catalog' GET '/api/data/v9.2/catalogs' $headers)
        Select-DataverseValue $Outputs eventCatalog DATAVERSE_EVENT_CATALOG 'catalog' $options uniquename displayname
    }
    $headers.catalog = $Outputs.eventCatalog
    $path = '/api/flow/$metadata.json/GetEntityListEnum'
    if ([string]::IsNullOrWhiteSpace([string]$Outputs.eventCategory)) {
        $headers.operation = 'GetCategories'
        $options = @(Invoke-DataverseSelector $Outputs 'category' POST $path $headers)
        Select-DataverseValue $Outputs eventCategory DATAVERSE_EVENT_CATEGORY 'category' $options uniqueName displayName
    }
    $headers.category = $Outputs.eventCategory
    if ([string]::IsNullOrWhiteSpace([string]$Outputs.eventTable)) {
        $headers.operation = 'GetEntitiesForActionTrigger'
        $options = @(Invoke-DataverseSelector $Outputs 'action table' POST $path $headers)
        Select-DataverseValue $Outputs eventTable DATAVERSE_EVENT_TABLE 'action table' $options primaryEntityLogicalName primaryEntityDisplayName
    }
    $headers.entity = $Outputs.eventTable
    if ([string]::IsNullOrWhiteSpace([string]$Outputs.eventAction)) {
        $headers.operation = 'GetActionsForActionTrigger'
        $options = @(Invoke-DataverseSelector $Outputs 'action' POST $path $headers)
        Select-DataverseValue $Outputs eventAction DATAVERSE_EVENT_ACTION 'action' $options SdkMessageName DisplayName
    }
}
