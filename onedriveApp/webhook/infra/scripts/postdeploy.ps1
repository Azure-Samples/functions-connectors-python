param([switch] $ForceLocalSettings)

# Post-deployment configuration for the onedriveApp.
#
# Uses the connector-namespace Azure CLI extension to authorize the OneDrive
# for Business connection, browse folders interactively, and create Connector
# Namespace trigger configs that POST to the Functions connector webhook URL.

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')

Write-Host "Post-deployment configuration..." -ForegroundColor Yellow

# --- Pre-flight: verify the connector-namespace CLI extension is installed ----
$extensionName = az extension show --name connector-namespace --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $extensionName) {
    throw "The 'connector-namespace' Azure CLI extension is required."
}

# --- Read azd outputs --------------------------------------------------------
$outputJson = azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Failed to read deployment outputs.' }
$outputs = ($outputJson -join "`n") | ConvertFrom-Json
if ($outputs -isnot [System.Management.Automation.PSCustomObject]) {
    throw 'Deployment outputs must be a JSON object.'
}
foreach ($key in @('resourceGroupName', 'connectorNamespaceName', 'connectorNamespaceConnectionName', 'functionAppName', 'functionAppDefaultHostname', 'AZURE_SUBSCRIPTION_ID')) {
    $value = $outputs.$key
    if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value) -or $value -eq 'null') {
        throw "Deployment output '$key' must be a nonempty string."
    }
}

$resourceGroupName      = $outputs.resourceGroupName
$connectorNamespaceName = $outputs.connectorNamespaceName
$onedriveConnectionName = $outputs.connectorNamespaceConnectionName
$functionAppName        = $outputs.functionAppName
$functionAppDefaultHostname = $outputs.functionAppDefaultHostname
$subscriptionId         = $outputs.AZURE_SUBSCRIPTION_ID
$onedriveFolderId       = if ($env:ONEDRIVE_FOLDER_ID) { $env:ONEDRIVE_FOLDER_ID } else { $outputs.ONEDRIVE_FOLDER_ID }

Write-LocalSettings @{
    FUNCTIONS_WORKER_RUNTIME = 'python'
    AzureWebJobsStorage = 'UseDevelopmentStorage=true'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'
} -ForceLocalSettings:$ForceLocalSettings

function Select-FromList {
    param(
        [Parameter(Mandatory)] [string] $Title,
        [Parameter(Mandatory)] [object[]] $Items,
        [Parameter(Mandatory)] [string] $LabelProperty,
        [string] $SubLabelProperty
    )

    Write-Host ""
    Write-Host $Title -ForegroundColor Cyan
    for ($i = 0; $i -lt $Items.Count; $i++) {
        $label = $Items[$i].$LabelProperty
        if ($SubLabelProperty -and $Items[$i].$SubLabelProperty) {
            Write-Host ("  [{0}] {1}  ({2})" -f ($i + 1), $label, $Items[$i].$SubLabelProperty)
        } else {
            Write-Host ("  [{0}] {1}" -f ($i + 1), $label)
        }
    }

    while ($true) {
        $answer = Read-Host "Enter number (1-$($Items.Count))"
        if ($null -eq $answer) {
            throw "No input available. Re-run with 'interactive: true' on the hook, or set ONEDRIVE_FOLDER_ID via 'azd env set'."
        }

        $num = 0
        if ([int]::TryParse($answer, [ref] $num) -and $num -ge 1 -and $num -le $Items.Count) {
            return $Items[$num - 1]
        }

        throw 'Invalid folder selection.'
    }
}

function Select-OneDriveFolderInteractive {
    param([string] $CurrentSavedId)

    $stack = New-Object System.Collections.Generic.Stack[object]
    $stack.Push([pscustomobject]@{ id = 'root'; path = '/' })

    while ($true) {
        $current = $stack.Peek()
        Write-Host ""
        Write-Host "Current folder: $($current.path)  [id: $($current.id)]" -ForegroundColor Cyan

        $listingPath = if ($current.id -eq 'root') {
            '/datasets/default/folders'
        } else {
            "/datasets/default/folders/$([Uri]::EscapeDataString($current.id))"
        }

        $requestFile = Join-Path ([IO.Path]::GetTempPath()) "onedrive-list-$([guid]::NewGuid()).json"
        $requestOwned = $false
        try {
            $stream = New-PrivateStagingStream $requestFile
            $requestOwned = $true
            try {
                $bytes = [Text.UTF8Encoding]::new($false).GetBytes((@{ method = 'get'; path = $listingPath } | ConvertTo-Json -Compress))
                $stream.Write($bytes, 0, $bytes.Length)
            } finally { $stream.Dispose() }
            $invokeRaw = az connector-namespace connection invoke `
                -g $resourceGroupName --namespace $connectorNamespaceName `
                --connection-name $onedriveConnectionName `
                --request "@$requestFile" -o json 2>$null | Out-String
            if ($LASTEXITCODE -ne 0 -or -not $invokeRaw) { throw 'Failed to list OneDrive folders.' }
        } finally {
            if ($requestOwned -and [IO.File]::Exists($requestFile)) { [IO.File]::Delete($requestFile) }
        }
        $invokeResponse = $invokeRaw | ConvertFrom-Json
        $statusCode = 0
        $rawStatusCode = [string] $invokeResponse.response.statusCode
        $success = if ([int]::TryParse($rawStatusCode, [ref] $statusCode)) {
            $statusCode -ge 200 -and $statusCode -lt 300
        } else {
            $rawStatusCode -in @('OK', 'Created', 'Accepted', 'NoContent')
        }

        if (-not $success) { throw "OneDrive folder listing returned status '$rawStatusCode'." }
        $body = $invokeResponse.response.body
        if ($body -is [string]) { $body = $body | ConvertFrom-Json -NoEnumerate }
        if ($body -is [System.Management.Automation.PSCustomObject] -and $body.PSObject.Properties['value']) {
            $body = $body.value
        }
        if ($body -isnot [array]) {
            throw 'OneDrive folder listing must contain an array.'
        }
        $subfolders = @($body | Where-Object { $_.IsFolder -eq $true })
        foreach ($folder in $subfolders) {
            if ($folder.Id -isnot [string] -or [string]::IsNullOrWhiteSpace($folder.Id)) {
                throw 'OneDrive returned a folder without a connector identifier.'
            }
        }

        $choices = @()
        $pickId = if ($current.id -eq 'root') { 'root' } else { $current.id }
        $choices += [pscustomobject]@{ display = "[OK] Use this folder ($($current.path))"; action = 'pick'; targetId = $pickId; target = $null }
        if ($CurrentSavedId -and $stack.Count -eq 1) {
            $choices += [pscustomobject]@{ display = "(keep current saved: $CurrentSavedId)"; action = 'keep'; targetId = $CurrentSavedId; target = $null }
        }
        if ($stack.Count -gt 1) {
            $choices += [pscustomobject]@{ display = '.. (go up)'; action = 'up'; targetId = $null; target = $null }
        }
        foreach ($sf in $subfolders) {
            $choices += [pscustomobject]@{
                display  = "-> $($sf.Name)"
                action   = 'down'
                targetId = $null
                target   = [pscustomobject]@{
                    id   = $sf.Id
                    path = if ($current.path -eq '/') { "/$($sf.Name)" } else { "$($current.path)/$($sf.Name)" }
                }
            }
        }
        $choices += [pscustomobject]@{ display = '(Enter folder id manually...)'; action = 'manual'; targetId = $null; target = $null }
        $choices += [pscustomobject]@{ display = '(Cancel - skip trigger creation)'; action = 'cancel'; targetId = $null; target = $null }

        $picked = Select-FromList -Title 'Choose an action:' -Items $choices -LabelProperty 'display'
        switch ($picked.action) {
            'pick' { return $picked.targetId }
            'keep' { return $picked.targetId }
            'up' { [void] $stack.Pop() }
            'down' { $stack.Push($picked.target) }
            'manual' {
                $manual = Read-Host 'OneDrive folder id'
                if (-not [string]::IsNullOrWhiteSpace($manual)) {
                    return $manual
                }
                throw 'A connector folder identifier is required.'
            }
            'cancel' { throw 'Folder selection canceled. No trigger configs were created.' }
        }
    }
}

Write-Host ""
if ($onedriveFolderId) {
    Write-Host "Current ONEDRIVE_FOLDER_ID: $onedriveFolderId" -ForegroundColor DarkGray
}

# --- Authorize the OneDrive connection (OAuth consent) ----------------------
Write-Host ""
Write-Host "Authorizing OneDrive for Business connection..." -ForegroundColor Yellow

$currentStatus = az connector-namespace connection show `
    -g $resourceGroupName --namespace $connectorNamespaceName `
    -n $onedriveConnectionName `
    --query "properties.overallStatus" -o tsv 2>$null

if ($LASTEXITCODE -ne 0) { throw 'Failed to read the OneDrive connection status.' }

if ($currentStatus -and $currentStatus.ToLower() -eq 'connected') {
    Write-Host "   already Connected; skipping consent flow" -ForegroundColor Green
} else {
    $consentParameters = "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]"
    $consentJson = $null
    $link = $null

    for ($i = 0; $i -lt 5; $i++) {
        $consentJson = az connector-namespace connection list-consent-links `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            --connection-name $onedriveConnectionName `
            --parameters $consentParameters `
            -o json 2>$null | Out-String
        if ($LASTEXITCODE -eq 0 -and $consentJson) {
            $link = az connector-namespace connection list-consent-links `
                -g $resourceGroupName --namespace $connectorNamespaceName `
                --connection-name $onedriveConnectionName `
                --parameters $consentParameters `
                --query "value[0].link" -o tsv 2>$null
            if ($LASTEXITCODE -ne 0) { $link = $null }
            if (-not $link -or $link -eq 'null') {
                $link = az connector-namespace connection list-consent-links `
                    -g $resourceGroupName --namespace $connectorNamespaceName `
                    --connection-name $onedriveConnectionName `
                    --parameters $consentParameters `
                    --query "link" -o tsv 2>$null
                    if ($LASTEXITCODE -ne 0) { $link = $null }
            }
                    if ($link -and $link -ne 'null') { break }
        }

        Write-Host "   list-consent-links attempt $($i + 1) failed; retrying in 5s..." -ForegroundColor Yellow
        if ($i -lt 4) { Start-Sleep -Seconds 5 }
    }

    if (-not $consentJson) {
        throw 'Consent link acquisition failed after retries.'
    }

    if (-not $link -or $link -eq 'null') {
        throw 'Consent link acquisition returned no link.'
    }

    Write-Host "   opening browser for OAuth consent..." -ForegroundColor Cyan
    Write-Host "   (if no tab opens, paste this URL manually: $link)" -ForegroundColor Cyan
    try { Start-Process $link | Out-Null } catch { Write-Host "   Start-Process failed: $_" -ForegroundColor Yellow }

    $deadline = (Get-Date).AddMinutes(5)
    $lastStatus = ''
    $authorized = $false
    while ((Get-Date) -lt $deadline) {
        $status = az connector-namespace connection show `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $onedriveConnectionName `
            --query "properties.overallStatus" -o tsv 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'Failed to read the OneDrive connection status.' }
        if ($status -ne $lastStatus) {
            Write-Host "   status: $(if ($status) { $status } else { '?' })" -ForegroundColor Cyan
            $lastStatus = $status
        }
        if ($status -and $status.ToLower() -eq 'connected') {
            Write-Host "   Connection authenticated" -ForegroundColor Green
            $authorized = $true
            break
        }
        Start-Sleep -Seconds 3
    }

    if (-not $authorized) {
        throw 'OneDrive connection did not reach Connected. Complete consent and re-run the hook.'
    }
}

# --- Select OneDrive folder -------------------------------------------------
if (-not $onedriveFolderId) {
    Write-Host 'Listing OneDrive folders via the authorized connection...'
    $onedriveFolderId = Select-OneDriveFolderInteractive
}

if ($onedriveFolderId -isnot [string] -or [string]::IsNullOrWhiteSpace($onedriveFolderId) -or $onedriveFolderId -eq 'null') {
    throw 'Set ONEDRIVE_FOLDER_ID to a connector folder identifier or root, not a display path.'
}
azd env set ONEDRIVE_FOLDER_ID $onedriveFolderId | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Failed to save ONEDRIVE_FOLDER_ID.' }
Write-Host "Saved ONEDRIVE_FOLDER_ID=$onedriveFolderId" -ForegroundColor Green

# --- Create Connector Namespace trigger configs -----------------------------
Write-Host ""
Write-Host "Fetching connector extension key for $functionAppName..." -ForegroundColor Cyan
$rawTriggers = az connector-namespace trigger list -g $resourceGroupName --namespace $connectorNamespaceName --query '[].name' -o json 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Could not list existing webhook trigger configurations.' }
$existingTriggers = ($rawTriggers -join "`n") | ConvertFrom-Json -NoEnumerate
if ($existingTriggers -isnot [array] -or @($existingTriggers | Where-Object { $_ -isnot [string] -or [string]::IsNullOrWhiteSpace($_) }).Count) {
    throw 'Invalid trigger list response.'
}
$connectorExtensionKey = az functionapp keys list -g $resourceGroupName -n $functionAppName --query "systemKeys.connector_extension" -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($connectorExtensionKey) -or $connectorExtensionKey -eq 'null') {
    throw 'Could not fetch the connector_extension system key.'
}

$triggers = @(
    @{ functionName = 'OnOneDriveNewFile'; operationName = 'OnNewFilesV2' },
    @{ functionName = 'OnOneDriveUpdatedFile'; operationName = 'OnUpdatedFilesV2' },
    @{ functionName = 'OnOneDriveNewFileContent'; operationName = 'OnNewFileV2' },
    @{ functionName = 'OnOneDriveUpdatedFileContent'; operationName = 'OnUpdatedFileV2' }
)

foreach ($trigger in $triggers) {
    $functionName = $trigger.functionName
    $operationName = $trigger.operationName
    $triggerName = "$onedriveConnectionName-$($functionName.ToLowerInvariant())"
    $callbackUrl = "https://$functionAppDefaultHostname/runtime/webhooks/connector?functionName=$functionName"
    $notifFile = Join-Path ([IO.Path]::GetTempPath()) "onedrive-notification-$([guid]::NewGuid()).json"
    $parametersFile = Join-Path ([IO.Path]::GetTempPath()) "onedrive-parameters-$([guid]::NewGuid()).json"
    $connectionFile = Join-Path ([IO.Path]::GetTempPath()) "onedrive-connection-$([guid]::NewGuid()).json"
    $metadataFile = Join-Path ([IO.Path]::GetTempPath()) "onedrive-metadata-$([guid]::NewGuid()).json"
    $ownedFiles = [Collections.Generic.List[string]]::new()
    $failure = $null
    $notification = @{
        callbackUrl = $callbackUrl
        authentication = @{
            type = "QueryString"
            name = "code"
            value = $connectorExtensionKey
        }
    }

    Write-Host ""
    Write-Host "Creating trigger '$triggerName' for $functionName ($operationName)..." -ForegroundColor Yellow

    try {
        foreach ($document in @(
            @{ path = $notifFile; value = $notification },
            @{ path = $parametersFile; value = @(@{ name = 'folderId'; value = $onedriveFolderId }) },
            @{ path = $connectionFile; value = @{ connectionName = $onedriveConnectionName; connectorName = 'onedriveforbusiness' } },
            @{ path = $metadataFile; value = @{ destinationType = 'functionApp'; functionAppName = $functionAppName; functionAppResourceGroup = $resourceGroupName; functionAppSubscriptionId = $subscriptionId; functionName = $functionName; recurrenceFrequency = 'Minute'; recurrenceInterval = '5' } }
        )) {
            $stream = New-PrivateStagingStream $document.path
            $ownedFiles.Add($document.path)
            try {
                $bytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $document.value -Depth 5 -Compress))
                $stream.Write($bytes, 0, $bytes.Length)
                $stream.Flush($true)
            } finally { $stream.Dispose() }
        }
        $verb = if ($triggerName -in $existingTriggers) { 'update' } else { 'create' }
        az connector-namespace trigger $verb `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $triggerName `
            --connection-details "@$connectionFile" `
            --operation-name $operationName `
            --parameters "@$parametersFile" `
            --notification-details "@$notifFile" `
            --state Enabled `
            --description "OneDrive $operationName -> $functionName" `
            --metadata "@$metadataFile" `
            -o none 2>$null | Out-Null

        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create trigger '$triggerName'."
        }
    } catch { $failure = $_; throw }
    finally {
        $cleanupFailed = $false
        foreach ($path in $ownedFiles) {
            try { if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) } }
            catch { $cleanupFailed = $true; Write-Warning 'Could not clean owned callback staging file.' }
        }
        if ($cleanupFailed -and $null -eq $failure) { throw 'Callback staging cleanup failed.' }
    }
}

Write-Host ""
Write-Host 'All four Connector Namespace trigger configs created successfully.' -ForegroundColor Green

Write-Host ""
Write-Host "Post-deployment configuration complete." -ForegroundColor Green
Write-Host ""
