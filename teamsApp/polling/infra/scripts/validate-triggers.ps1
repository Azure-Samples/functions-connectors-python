param([string] $Path = (Join-Path $PSScriptRoot '../additional-triggers.json'))

$ErrorActionPreference = 'Stop'
$triggers = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -NoEnumerate
if ($triggers -isnot [array]) {
    throw 'Additional trigger configuration must be a JSON array.'
}
$requiredParameters = @{
    WebhookChatMessageTrigger = @()
    WebhookNewMessageTrigger = @('threadType', 'requestBody')
    WebhookAtMentionTrigger = @('threadType', 'requestBody')
    WebhookKeywordTrigger = @('threadType', '$search', 'requestBody')
    WebhookMessageReactionTrigger = @('reactionKey', 'frequency', 'runningPolicy', 'threadType', 'requestBody')
    RecordingTrigger = @('scopeType', 'body')
    TranscriptTrigger = @('scopeType', 'body')
}
$seenOperations = @{}
foreach ($trigger in $triggers) {
    if ($requiredParameters.Keys -cnotcontains $trigger.functionName -or $seenOperations.ContainsKey($trigger.functionName)) {
        throw "Unsupported or duplicate additional event: $($trigger.functionName)"
    }
    $seenOperations[$trigger.functionName] = $true
    if ($trigger.parameters -isnot [array]) {
        throw "Event $($trigger.functionName) requires a parameters array."
    }
    $seenParameters = @{}
    foreach ($parameter in $trigger.parameters) {
        if ($requiredParameters[$trigger.functionName] -cnotcontains $parameter.name -or
            $seenParameters.ContainsKey($parameter.name)) {
            throw "Event $($trigger.functionName) has an unsupported, incorrectly cased or duplicate parameter: $($parameter.name)"
        }
        $seenParameters[$parameter.name] = $true
        $value = $parameter.value | ConvertTo-Json -Depth 30 -Compress
        if ($null -eq $parameter.value -or [string]::IsNullOrWhiteSpace([string]$parameter.value) -or
            $value -in @('{}', '[]') -or $value -match '<[^>]+>') {
            throw "Event $($trigger.functionName) requires a real value for $($parameter.name)."
        }
    }
    foreach ($name in $requiredParameters[$trigger.functionName]) {
        if (-not $seenParameters.ContainsKey($name)) {
            throw "Event $($trigger.functionName) requires parameter $name."
        }
    }
}
Write-Host "Validated $($triggers.Count) additional Teams events."