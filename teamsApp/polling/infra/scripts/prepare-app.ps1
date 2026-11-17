param([switch] $ForceLocalSettings, [switch] $LocalSettingsOnly)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
$developerCli = (Get-Command azd -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source

function Invoke-AzureCli {
    param([string[]] $Arguments)
    $result = & $azureCli @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI command '$($Arguments[0])' failed. No command output was logged." }
    return $result
}

$raw = & $developerCli env get-values --output json 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Could not read the selected azd environment.' }
$outputs = ($raw -join "`n") | ConvertFrom-Json
foreach ($name in @('AZURE_SUBSCRIPTION_ID', 'resourceGroupName', 'connectorNamespaceName', 'connectorNamespaceConnectionName',
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

if ($LocalSettingsOnly) {
    Write-LocalSettings $localValues -Force:$ForceLocalSettings
    return
}
& (Join-Path $PSScriptRoot 'validate-triggers.ps1')
$azureCli = (Get-Command az -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$extension = Invoke-AzureCli -Arguments @('extension', 'show', '--name', 'connector-namespace', '--query', 'name', '-o', 'tsv')
if (($extension -join '').Trim() -ne 'connector-namespace') {
    throw 'Install the connector-namespace Azure CLI extension before running this script.'
}

$optionalOperations = @(
    'WebhookChatMessageTrigger', 'WebhookNewMessageTrigger', 'WebhookAtMentionTrigger', 'WebhookKeywordTrigger',
    'WebhookMessageReactionTrigger', 'RecordingTrigger', 'TranscriptTrigger')
$deselectedOperations = @($optionalOperations | Where-Object {
    $triggerSettings."AzureWebJobs.$_.Disabled" -ceq 'true'
})
if ($deselectedOperations.Count -gt 0) {
    $namespaceOutput = Invoke-AzureCli -Arguments @('resource', 'show', '--subscription', $outputs.AZURE_SUBSCRIPTION_ID,
        '-g', $outputs.resourceGroupName,
        '-n', $outputs.connectorNamespaceName, '--resource-type', 'Microsoft.Web/connectorGateways',
        '--api-version', '2026-05-01-preview', '--query', 'id', '-o', 'tsv')
    $namespaceId = ($namespaceOutput -join '').Trim()
    $expectedId = "/subscriptions/$($outputs.AZURE_SUBSCRIPTION_ID)/resourceGroups/$($outputs.resourceGroupName)" +
        "/providers/Microsoft.Web/connectorGateways/$($outputs.connectorNamespaceName)"
    if ($namespaceId -ine $expectedId -or
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
