param([switch] $ForceLocalSettings)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'local-settings.ps1')
& (Join-Path $PSScriptRoot 'validate-triggers.ps1')
$additionalTriggers = Get-Content -LiteralPath (Join-Path $PSScriptRoot '../additional-triggers.json') -Raw |
    ConvertFrom-Json -NoEnumerate
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
$rawOutputs = & $developerCli env get-values --output json 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Could not read the selected azd environment.' }
$outputs = ($rawOutputs -join "`n") | ConvertFrom-Json
foreach ($name in @('resourceGroupName', 'connectorNamespaceName', 'connectorNamespaceConnectionName',
    'functionAppName', 'functionAppDefaultHostname', 'AZURE_SUBSCRIPTION_ID')) {
    if ([string]::IsNullOrWhiteSpace([string]$outputs.$name)) { throw "Missing azd output $name. Run azd provision first." }
}
if ([Uri]::CheckHostName($outputs.functionAppDefaultHostname) -ne [UriHostNameType]::Dns) {
    throw 'The Function App output must contain its actual default hostname.'
}

$localValues = @{
    AzureWebJobsStorage = 'UseDevelopmentStorage=true'
    FUNCTIONS_WORKER_RUNTIME = 'python'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES = '1'
}
foreach ($operation in @('WebhookChatMessageTrigger', 'WebhookNewMessageTrigger', 'WebhookAtMentionTrigger',
    'WebhookKeywordTrigger', 'WebhookMessageReactionTrigger', 'RecordingTrigger', 'TranscriptTrigger')) {
    $localValues["AzureWebJobs.$operation.Disabled"] = if ($additionalTriggers.functionName -ccontains $operation) { 'false' } else { 'true' }
}
Write-LocalSettings $localValues -Force:$ForceLocalSettings

$resourceGroupName = $outputs.resourceGroupName
$connectorNamespaceName = $outputs.connectorNamespaceName
$connectorNamespaceConnectionName = $outputs.connectorNamespaceConnectionName
$functionAppName = $outputs.functionAppName
$functionAppHostname = $outputs.functionAppDefaultHostname
$subscriptionId = $outputs.AZURE_SUBSCRIPTION_ID
$teamsGroupId = $outputs.TEAMS_GROUP_ID
$teamsChannelId = $outputs.TEAMS_CHANNEL_ID

function Select-FromList {
    param([string] $Title, [object[]] $Items, [string] $LabelProperty)
    Write-Host $Title
    for ($index = 0; $index -lt $Items.Count; $index++) {
        Write-Host ('  [{0}] {1}' -f ($index + 1), $Items[$index].$LabelProperty)
    }
    while ($true) {
        $answer = Read-Host "Enter number (1-$($Items.Count))"
        if ($null -eq $answer) { throw 'No input available. Set TEAMS_GROUP_ID and TEAMS_CHANNEL_ID in the azd environment.' }
        $number = 0
        if ([int]::TryParse($answer, [ref]$number) -and $number -ge 1 -and $number -le $Items.Count) {
            return $Items[$number - 1]
        }
        Write-Host 'Invalid selection.'
    }
}

function Invoke-Graph {
    param([string] $Url)
    $raw = Invoke-AzureCli -Arguments @('rest', '--method', 'get', '--url', $Url, '--resource', 'https://graph.microsoft.com')
    return ($raw -join "`n") | ConvertFrom-Json
}

if (-not $teamsGroupId) {
    $teamsResponse = Invoke-Graph -Url 'https://graph.microsoft.com/v1.0/me/joinedTeams?$select=id,displayName'
    if (-not $teamsResponse.value) { throw 'Could not list joined teams. Set TEAMS_GROUP_ID and TEAMS_CHANNEL_ID in the azd environment.' }
    $team = Select-FromList -Title 'Select a team:' -Items $teamsResponse.value -LabelProperty 'displayName'
    $teamsGroupId = $team.id
    & $developerCli env set TEAMS_GROUP_ID $teamsGroupId 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not save TEAMS_GROUP_ID.' }
}
if (-not $teamsChannelId) {
    $channelsResponse = Invoke-Graph -Url "https://graph.microsoft.com/v1.0/teams/$teamsGroupId/channels?`$select=id,displayName"
    if (-not $channelsResponse.value) { throw 'Could not list channels. Set TEAMS_CHANNEL_ID in the azd environment.' }
    $channel = Select-FromList -Title 'Select a channel:' -Items $channelsResponse.value -LabelProperty 'displayName'
    $teamsChannelId = $channel.id
    & $developerCli env set TEAMS_CHANNEL_ID $teamsChannelId 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not save TEAMS_CHANNEL_ID.' }
}

$existingRaw = Invoke-AzureCli -Arguments @('connector-namespace', 'trigger', 'list', '-g', $resourceGroupName,
    '--namespace', $connectorNamespaceName, '--query', '[].name', '-o', 'json')
$existingTriggers = ($existingRaw -join "`n") | ConvertFrom-Json -NoEnumerate
if ($existingTriggers -isnot [array] -or
    @($existingTriggers | Where-Object { $_ -isnot [string] -or [string]::IsNullOrWhiteSpace($_) }).Count -or
    @($existingTriggers | Select-Object -Unique).Count -ne $existingTriggers.Count) {
    throw 'Invalid Teams trigger list response.'
}
$connectorExtensionKey = $null
try {
    $keyOutput = Invoke-AzureCli -Arguments @('functionapp', 'keys', 'list', '-g', $resourceGroupName,
        '-n', $functionAppName, '--query', 'systemKeys.connector_extension', '-o', 'tsv')
    $connectorExtensionKey = ($keyOutput -join '').Trim()
    if ([string]::IsNullOrWhiteSpace($connectorExtensionKey) -or $connectorExtensionKey -eq 'null') {
        throw 'Could not obtain the connector extension system key. Deploy the Function App before registering callbacks.'
    }

    function New-TriggerConfig {
        param([string] $FunctionName, [string] $Description, [object[]] $Parameters = @())
        $triggerName = "$connectorNamespaceConnectionName-$($FunctionName.ToLowerInvariant())"
        $parametersFile = Join-Path $PSScriptRoot ".trigger-parameters-$([Guid]::NewGuid().ToString('N')).json"
        $notificationFile = Join-Path $PSScriptRoot ".notification-details-$([Guid]::NewGuid().ToString('N')).json"
        $ownedFiles = [Collections.Generic.List[string]]::new()
        $failure = $null
        try {
            $notification = @{
                callbackUrl = "https://$functionAppHostname/runtime/webhooks/connector?functionName=$FunctionName"
                authentication = @{ type = 'QueryString'; name = 'code'; value = $connectorExtensionKey }
            }
            foreach ($document in @(
                @{ path = $parametersFile; value = @($Parameters) },
                @{ path = $notificationFile; value = $notification })) {
                $stream = New-PrivateStagingStream $document.path
                $ownedFiles.Add($document.path)
                $streamFailure = $null
                try {
                    $json = ConvertTo-Json -InputObject $document.value -Depth 30 -Compress
                    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json)
                    $stream.Write($bytes)
                    $stream.Flush($true)
                } catch { $streamFailure = $_; throw }
                finally {
                    try { $stream.Dispose() }
                    catch {
                        if ($null -eq $streamFailure) { throw 'Could not close owned callback staging stream.' }
                        Write-Warning 'Could not close owned staging stream; original failure preserved.'
                    }
                }
            }
            $verb = if ($triggerName -in $existingTriggers) { 'update' } else { 'create' }
            Invoke-AzureCli -Arguments @('connector-namespace', 'trigger', $verb, '-g', $resourceGroupName,
                '--namespace', $connectorNamespaceName, '-n', $triggerName,
                '--connection-details', "{connectionName:$connectorNamespaceConnectionName,connectorName:teams}",
                '--operation-name', $FunctionName, '--parameters', "@$parametersFile",
                '--notification-details', "@$notificationFile", '--state', 'Enabled', '--description', $Description,
                '--metadata', "{destinationType:functionApp,functionAppName:$functionAppName,functionAppResourceGroup:$resourceGroupName,functionAppSubscriptionId:$subscriptionId,functionName:$FunctionName,recurrenceFrequency:Minute,recurrenceInterval:'5'}",
                '-o', 'none') | Out-Null
        }
        catch { $failure = $_; throw }
        finally {
            $notification = $null
            $cleanupFailed = $false
            foreach ($path in $ownedFiles) {
                try { if ([IO.File]::Exists($path)) { [IO.File]::Delete($path) } }
                catch { $cleanupFailed = $true; Write-Warning 'Could not clean owned callback staging file.' }
            }
            if ($cleanupFailed -and $null -eq $failure) { throw 'Callback staging cleanup failed.' }
        }
    }

    $channelParameters = @(@{ name = 'groupId'; value = $teamsGroupId }, @{ name = 'channelId'; value = $teamsChannelId })
    $membershipParameters = @(@{ name = 'groupId'; value = $teamsGroupId })
    New-TriggerConfig -FunctionName 'OnNewChannelMessage' -Description 'When a new channel message is added' -Parameters $channelParameters
    New-TriggerConfig -FunctionName 'OnNewChannelMessageMentioningMe' -Description 'When I am mentioned in a channel message' -Parameters $channelParameters
    New-TriggerConfig -FunctionName 'OnGroupMembershipAdd' -Description 'When a new team member is added' -Parameters $membershipParameters
    New-TriggerConfig -FunctionName 'OnGroupMembershipRemoval' -Description 'When a team member is removed' -Parameters $membershipParameters
    foreach ($trigger in $additionalTriggers) {
        New-TriggerConfig -FunctionName $trigger.functionName -Description "Teams $($trigger.functionName) event" -Parameters @($trigger.parameters)
    }
    Write-Host 'All selected trigger configs configured without deleting existing registrations.'
}
finally {
    $connectorExtensionKey = $null
    $keyOutput = $null
}

function Get-ConnectionStatus {
    $status = Invoke-AzureCli -Arguments @('connector-namespace', 'connection', 'show', '-g', $resourceGroupName,
        '--namespace', $connectorNamespaceName, '-n', $connectorNamespaceConnectionName,
        '--query', 'properties.overallStatus', '-o', 'tsv')
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
            '-g', $resourceGroupName, '--namespace', $connectorNamespaceName,
            '--connection-name', $connectorNamespaceConnectionName,
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
            Write-Host 'Teams connection authorized. All selected Teams triggers are configured.'
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