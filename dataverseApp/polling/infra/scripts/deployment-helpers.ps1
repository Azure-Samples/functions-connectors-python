. (Join-Path $PSScriptRoot 'action-cleanup.ps1')

function Get-DataverseConfigurations {
    param([string] $CollectionUri)
    $nextLink = "${CollectionUri}?api-version=2026-05-01-preview"
    $visited = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    while ($nextLink) {
        $pageUri = [uri]$nextLink
        if (-not $pageUri.IsAbsoluteUri -or $pageUri.Scheme -ne 'https' -or
            $pageUri.Host -ne 'management.azure.com' -or $pageUri.Port -ne 443 -or
            $pageUri.UserInfo -or $pageUri.Fragment -or
            $pageUri.AbsolutePath.TrimEnd('/') -ine ([uri]$CollectionUri).AbsolutePath -or -not $visited.Add($nextLink)) {
            throw 'Invalid or repeated trigger configuration continuation URL.'
        }
        $path = Join-Path ([IO.Path]::GetTempPath()) "dataverse-inventory-$([guid]::NewGuid().ToString('N')).json"
        $owned = $false
        $failure = $null
        try {
            $stream = New-PrivateStagingStream $path
            $owned = $true
            $stream.Dispose()
            az rest --method get --url $nextLink --output-file $path -o none 2>$null
            if ($LASTEXITCODE -ne 0) { throw 'Could not inspect existing Dataverse subscriptions.' }
            $json = Get-Content -LiteralPath $path -Raw -Encoding utf8
            $page = $json | ConvertFrom-Json -AsHashtable -Depth 100
            if ($null -eq $page.value) { throw 'Invalid trigger configuration list response.' }
            $options = [System.Text.Json.JsonDocumentOptions]::new()
            $options.MaxDepth = 100
            $dom = [System.Text.Json.Nodes.JsonNode]::Parse($json, $null, $options)
            foreach ($node in $dom['value'].AsArray()) {
                @{ config = ($node.ToJsonString() | ConvertFrom-Json -AsHashtable -Depth 100); node = $node }
            }
            $nextLink = [string]$page.nextLink
        } catch { $failure = $_; throw } finally {
            try { if ($owned -and [IO.File]::Exists($path)) { [IO.File]::Delete($path) } } catch {
                if ($null -eq $failure) { throw 'Could not clean private Dataverse inventory staging file.' }
                Write-Warning 'Could not clean private inventory staging file; original failure preserved.'
            }
        }
    }
}

function Connect-Dataverse {
    param($Outputs)
    function Get-Status {
        $status = az connector-namespace connection show -g $Outputs.resourceGroupName --namespace $Outputs.connectorNamespaceName `
            -n $Outputs.connectorNamespaceConnectionName --query properties.overallStatus -o tsv 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$status)) { throw 'Could not read the Dataverse connection status.' }
        return ([string]$status).Trim()
    }
    if ((Get-Status) -eq 'Connected') { Write-Host 'Dataverse connection is already authorized; preserving OAuth consent.'; return }
    $link = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        foreach ($query in @('value[0].link', 'link')) {
            $link = az connector-namespace connection list-consent-links -g $Outputs.resourceGroupName --namespace $Outputs.connectorNamespaceName `
                --connection-name $Outputs.connectorNamespaceConnectionName --parameters "[{parameterName:token,redirectUrl:'https://connectors.azure.com'}]" `
                --query $query -o tsv 2>$null
            if ($LASTEXITCODE -ne 0) { throw 'Could not request a Dataverse consent link.' }
            if ($link -and $link -ne 'null') { break }
        }
        if ($link -and $link -ne 'null') { break }
        if ($attempt -lt 5) { Start-Sleep -Seconds 5 }
    }
    if (-not $link -or $link -eq 'null') { throw 'Could not obtain a Dataverse consent link.' }
    $consent = [uri]$link
    if (-not $consent.IsAbsoluteUri -or $consent.Scheme -ne 'https' -or $consent.UserInfo) { throw 'Invalid Dataverse consent URL.' }
    Write-Host 'Open the Dataverse consent page in your browser; the consent URL is not logged.'
    Start-Process $link | Out-Null
    $deadline = (Get-Date).AddMinutes(5)
    while ((Get-Status) -ne 'Connected') {
        if ((Get-Date) -ge $deadline) { throw 'Timed out waiting for Dataverse OAuth consent.' }
        Start-Sleep -Seconds 3
    }
}

function Test-DataverseSourceStatus {
    param([string] $CollectionUri, [string[]] $Names)
    foreach ($name in $Names) {
        $raw = az rest --method get --url "$CollectionUri/$name/triggerStatuses/latest?api-version=2026-05-01-preview" `
            --query '{status:lastExecutionStatus,code:lastExecutionStatusCode,started:lastExecutionStartTime,error:lastExecutionError}' -o json 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Could not read source status for '$name'; inspect Connector Namespace before testing events." }
        $status = ($raw -join "`n") | ConvertFrom-Json -AsHashtable
        if ($status.status -eq 'Failed' -or $status.error.Count -gt 0) {
            throw "Dataverse source execution failed for '$name'. Inspect its Connector Namespace trigger status; details were not logged."
        }
        if ($status.started -and ($status.status -eq 'Succeeded' -or ($status.status -eq 'Skipped' -and $status.code -in @('Accepted', 'OK')))) {
            Write-Host "Latest source execution succeeded for '$name'; event delivery is not verified."
        } else { Write-Warning "Source registration/execution for '$name' is pending or unverified. Rerun the hook after initialization." }
    }
}