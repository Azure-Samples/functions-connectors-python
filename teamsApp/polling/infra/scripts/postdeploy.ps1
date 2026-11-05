param([switch] $ForceLocalSettings)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
& (Join-Path $PSScriptRoot 'validate-triggers.ps1')
$azureCli = (Get-Command az -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$developerCli = (Get-Command azd -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source

function Invoke-AzureCli {
    param([string[]] $Arguments)
    $result = & $azureCli @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI command '$($Arguments[0])' failed. No command output was logged." }
    return $result
}

$extension = Invoke-AzureCli -Arguments @('extension', 'show', '--name', 'connector-namespace', '--query', 'name', '-o', 'tsv')
if (($extension -join '').Trim() -ne 'connector-namespace') {
    throw 'Install the connector-namespace Azure CLI extension before running this script.'
}
$raw = & $developerCli env get-values --output json 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Could not read the selected azd environment.' }
$outputs = ($raw -join "`n") | ConvertFrom-Json
foreach ($name in @('resourceGroupName', 'connectorNamespaceName', 'connectorNamespaceConnectionName',
    'connectorPollingEndpoint', 'triggerConfigSettings')) {
    if ([string]::IsNullOrWhiteSpace([string]$outputs.$name)) {
        throw "Missing azd output $name. Run azd provision first."
    }
}

$triggerSettings = if ($outputs.triggerConfigSettings -is [string]) {
    $outputs.triggerConfigSettings | ConvertFrom-Json
} else {
    $outputs.triggerConfigSettings
}
$localValues = @{
    AzureWebJobsStorage = 'UseDevelopmentStorage=true'
    FUNCTIONS_WORKER_RUNTIME = 'python'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'
    ConnectorNamespace__pollingEndpoint = $outputs.connectorPollingEndpoint
}
foreach ($functionName in @(
    'OnNewChannelMessage', 'OnNewChannelMessageMentioningMe', 'OnGroupMembershipAdd', 'OnGroupMembershipRemoval',
    'WebhookChatMessageTrigger', 'WebhookNewMessageTrigger', 'WebhookAtMentionTrigger', 'WebhookKeywordTrigger',
    'WebhookMessageReactionTrigger', 'RecordingTrigger', 'TranscriptTrigger')) {
    $setting = "${functionName}TriggerConfigName"
    if ($triggerSettings.$setting -isnot [string] -or [string]::IsNullOrWhiteSpace($triggerSettings.$setting)) {
        throw "Missing trigger configuration setting $setting."
    }
    $localValues[$setting] = $triggerSettings.$setting
}
foreach ($functionName in @(
    'WebhookChatMessageTrigger', 'WebhookNewMessageTrigger', 'WebhookAtMentionTrigger', 'WebhookKeywordTrigger',
    'WebhookMessageReactionTrigger', 'RecordingTrigger', 'TranscriptTrigger')) {
    $setting = "AzureWebJobs.$functionName.Disabled"
    if ($triggerSettings.$setting -isnot [string] -or $triggerSettings.$setting -cnotin @('true', 'false')) {
        throw "Missing or invalid function enablement setting $setting."
    }
    $localValues[$setting] = $triggerSettings.$setting
}

Write-LocalSettings $localValues -Force:$ForceLocalSettings

$optionalOperations = @(
    'WebhookChatMessageTrigger', 'WebhookNewMessageTrigger', 'WebhookAtMentionTrigger', 'WebhookKeywordTrigger',
    'WebhookMessageReactionTrigger', 'RecordingTrigger', 'TranscriptTrigger')
$deselectedOperations = @($optionalOperations | Where-Object {
    $triggerSettings."AzureWebJobs.$_.Disabled" -ceq 'true'
})
if ($deselectedOperations.Count -gt 0) {
    $namespaceOutput = Invoke-AzureCli -Arguments @('resource', 'show', '-g', $outputs.resourceGroupName,
        '-n', $outputs.connectorNamespaceName, '--resource-type', 'Microsoft.Web/connectorGateways',
        '--api-version', '2026-05-01-preview', '--query', 'id', '-o', 'tsv')
    $namespaceId = ($namespaceOutput -join '').Trim()
    $expectedScope = '/resourceGroups/' + [regex]::Escape($outputs.resourceGroupName) +
        '/providers/Microsoft.Web/connectorGateways/' + [regex]::Escape($outputs.connectorNamespaceName)
    if ($namespaceId -notmatch "^/subscriptions/[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$expectedScope$" -or
        $outputs.resourceGroupName -match '[/\\?#]' -or $outputs.connectorNamespaceName -match '[/\\?#]') {
        throw 'Invalid Teams Connector Namespace resource ID.'
    }
    foreach ($operation in $deselectedOperations) {
        $triggerName = "teams-$($operation.ToLowerInvariant())"
        $uri = "$namespaceId/triggerConfigs/${triggerName}?api-version=2026-05-01-preview"
        $readTemp = Join-Path ([IO.Path]::GetTempPath()) "teams-poll-read-$([guid]::NewGuid().ToString('N')).json"
        $temp = Join-Path ([IO.Path]::GetTempPath()) "teams-poll-state-$([guid]::NewGuid().ToString('N')).json"
        $ownedFiles = [Collections.Generic.List[string]]::new()
        $failure = $null
        try {
            $stream = New-PrivateStagingStream $readTemp
            $ownedFiles.Add($readTemp)
            $stream.Dispose()
            $response = & $azureCli rest --method get --url $uri --output-file $readTemp -o none 2>&1
            if ($LASTEXITCODE -ne 0) {
                if (($response -join "`n") -match '(?m)^ERROR:\s+Not Found\(|\((ResourceNotFound|NotFound)\)') { continue }
                throw "Could not read optional Teams Poll configuration $triggerName. No command output was logged."
            }
            $config = [System.Text.Json.Nodes.JsonNode]::Parse(
                [IO.File]::ReadAllText($readTemp, [Text.UTF8Encoding]::new($false, $true)))
            $properties = $config['properties']
            if ($properties -isnot [System.Text.Json.Nodes.JsonObject] -or
                [string]$properties['deliveryMode'] -cne 'Poll' -or [string]$properties['operationName'] -cne $operation -or
                [string]$properties['connectionDetails']['connectorName'] -cne 'teams' -or
                [string]$properties['connectionDetails']['connectionName'] -cne $outputs.connectorNamespaceConnectionName) {
                throw "Optional Teams configuration $triggerName is not the expected sample Poll configuration."
            }
            if ([string]$properties['state'] -ceq 'Disabled') { continue }
            $properties.Remove('provisioningState') | Out-Null
            $properties.Remove('pollingEndpoints') | Out-Null
            $properties['state'] = [System.Text.Json.Nodes.JsonValue]::Create('Disabled')
            $config.Remove('properties') | Out-Null
            $body = [System.Text.Json.Nodes.JsonObject]::new()
            $body.Add('properties', $properties)
            $stream = New-PrivateStagingStream $temp
            $ownedFiles.Add($temp)
            try {
                $bytes = [Text.UTF8Encoding]::new($false).GetBytes($body.ToJsonString())
                $stream.Write($bytes)
                $stream.Flush($true)
            } finally { $stream.Dispose() }
            Invoke-AzureCli -Arguments @('rest', '--method', 'put', '--url', $uri, '--body', "@$temp",
                '--headers', 'Content-Type=application/json', '-o', 'none') | Out-Null
            Write-Host "Disabled deselected Teams Poll configuration $triggerName."
        } catch { $failure = $_; throw }
        finally {
            $cleanupFailed = $false
            foreach ($path in $ownedFiles) {
                try { if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) } }
                catch { $cleanupFailed = $true; Write-Warning 'Could not clean owned Poll configuration staging file.' }
            }
            if ($cleanupFailed -and $null -eq $failure) { throw 'Could not clean owned Poll configuration staging files.' }
        }
    }
}

function Get-ConnectionStatus {
    $status = Invoke-AzureCli -Arguments @('connector-namespace', 'connection', 'show',
        '-g', $outputs.resourceGroupName, '--namespace', $outputs.connectorNamespaceName,
        '-n', $outputs.connectorNamespaceConnectionName, '--query', 'properties.overallStatus', '-o', 'tsv')
    if ([string]::IsNullOrWhiteSpace(($status -join ''))) { throw 'Could not read the Teams connection status.' }
    return ($status -join '').Trim()
}

if ((Get-ConnectionStatus) -eq 'Connected') {
    Write-Host 'Teams connection is already authorized.'
    return
}

Write-Host 'Authorize the Teams connection with the account whose teams to monitor.'
$consentLink = $null
try {
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $rawConsent = Invoke-AzureCli -Arguments @('connector-namespace', 'connection', 'list-consent-links',
            '-g', $outputs.resourceGroupName, '--namespace', $outputs.connectorNamespaceName,
            '--connection-name', $outputs.connectorNamespaceConnectionName,
            '--parameters', "[{parameterName:token,redirectUrl:'https://connectors.azure.com'}]", '-o', 'json')
        $consent = ($rawConsent -join "`n") | ConvertFrom-Json
        $consentLink = if ($consent.value) { $consent.value[0].link } else { $consent.link }
        if ($consentLink -and $consentLink -ne 'null') { break }
        if ($attempt -lt 5) { Start-Sleep -Seconds 5 }
    }
    if (-not $consentLink -or $consentLink -eq 'null') { throw 'Could not obtain a Teams consent link.' }
    try { Start-Process $consentLink | Out-Null }
    catch { throw 'Could not open the consent browser. Run the connection authorization flow interactively.' }

    $deadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Seconds 3
        if ((Get-ConnectionStatus) -eq 'Connected') {
            Write-Host 'Teams connection authorized. Poll trigger configurations are provisioned for the selected events.'
            return
        }
    } while ((Get-Date) -lt $deadline)
    throw 'Timed out waiting for the Teams connection to become Connected.'
}
finally {
    $consentLink = $null
    $consent = $null
    $rawConsent = $null
}