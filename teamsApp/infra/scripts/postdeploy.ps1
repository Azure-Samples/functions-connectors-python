Write-Host "Post-deployment configuration..." -ForegroundColor Yellow

if (-not (az extension show --name connector-namespace --query name -o tsv 2>$null)) {
    Write-Host "ERROR: The 'connector-namespace' Azure CLI extension is required." -ForegroundColor Red
    Write-Host "Install: irm https://aka.ms/connector-namespace-cli-install-ps | iex" -ForegroundColor Red
    exit 1
}

# Outputs from azd
$outputs = azd env get-values --output json | ConvertFrom-Json

$resourceGroupName = $outputs.resourceGroupName
$connectorNamespaceName = $outputs.connectorNamespaceName
$connectorNamespaceConnectionName = $outputs.connectorNamespaceConnectionName
$functionAppName = $outputs.functionAppName
$subscriptionId = $outputs.AZURE_SUBSCRIPTION_ID

# --- Required Teams identifiers ---
# Teams triggers are scoped to a specific team (and channel for message triggers).
# Read from azd env vars or prompt the user via Microsoft Graph.
$teamsGroupId   = $outputs.TEAMS_GROUP_ID
$teamsChannelId = $outputs.TEAMS_CHANNEL_ID

function Select-FromList {
    param(
        [Parameter(Mandatory)] [string] $Title,
        [Parameter(Mandatory)] [object[]] $Items,
        [Parameter(Mandatory)] [string] $LabelProperty
    )
    Write-Host ""
    Write-Host $Title -ForegroundColor Cyan
    for ($i = 0; $i -lt $Items.Count; $i++) {
        Write-Host ("  [{0}] {1}" -f ($i + 1), $Items[$i].$LabelProperty)
    }
    while ($true) {
        $answer = Read-Host "Enter number (1-$($Items.Count))"
        if ($null -eq $answer) {
            throw "No input available. Set TEAMS_GROUP_ID / TEAMS_CHANNEL_ID via 'azd env set'."
        }
        $num = 0
        if ([int]::TryParse($answer, [ref]$num) -and $num -ge 1 -and $num -le $Items.Count) {
            return $Items[$num - 1]
        }
        Write-Host "Invalid selection." -ForegroundColor Yellow
    }
}

function Invoke-Graph {
    param([Parameter(Mandatory)][string] $Url)
    $raw = az rest --method get --url $Url --resource https://graph.microsoft.com 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
    return ($raw | ConvertFrom-Json)
}

function Get-ConnectionOverallStatus {
    $status = az connector-namespace connection show `
        -g $resourceGroupName --namespace $connectorNamespaceName `
        -n $connectorNamespaceConnectionName `
        --query "properties.overallStatus" -o tsv 2>$null

    if ($LASTEXITCODE -ne 0 -or -not $status) { return $null }
    return $status
}

if (-not $teamsGroupId -or -not $teamsChannelId) {
    Write-Host ""
    Write-Host "TEAMS_GROUP_ID / TEAMS_CHANNEL_ID not set. Fetching your Teams from Microsoft Graph..." -ForegroundColor Yellow

    $teamsResponse = Invoke-Graph -Url 'https://graph.microsoft.com/v1.0/me/joinedTeams?$select=id,displayName'
    if (-not $teamsResponse -or -not $teamsResponse.value -or $teamsResponse.value.Count -eq 0) {
        Write-Host "ERROR: Could not list your joined teams via Microsoft Graph." -ForegroundColor Red
        Write-Host "       Set the values manually:" -ForegroundColor Red
        Write-Host "         azd env set TEAMS_GROUP_ID   <team / M365 group object id>" -ForegroundColor Red
        Write-Host "         azd env set TEAMS_CHANNEL_ID <channel id>" -ForegroundColor Red
        exit 1
    }

    if (-not $teamsGroupId) {
        $team = Select-FromList -Title 'Select a team:' -Items $teamsResponse.value -LabelProperty 'displayName'
        $teamsGroupId = $team.id
        azd env set TEAMS_GROUP_ID $teamsGroupId | Out-Null
        Write-Host "Saved TEAMS_GROUP_ID=$teamsGroupId" -ForegroundColor Green
    }

    if (-not $teamsChannelId) {
        $channelsResponse = Invoke-Graph -Url "https://graph.microsoft.com/v1.0/teams/$teamsGroupId/channels?`$select=id,displayName"
        if (-not $channelsResponse -or -not $channelsResponse.value -or $channelsResponse.value.Count -eq 0) {
            Write-Host "ERROR: Could not list channels for team $teamsGroupId." -ForegroundColor Red
            exit 1
        }
        $channel = Select-FromList -Title 'Select a channel:' -Items $channelsResponse.value -LabelProperty 'displayName'
        $teamsChannelId = $channel.id
        azd env set TEAMS_CHANNEL_ID $teamsChannelId | Out-Null
        Write-Host "Saved TEAMS_CHANNEL_ID=$teamsChannelId" -ForegroundColor Green
    }
}

# Fetch the connector extension system key
Write-Host "Fetching connector extension key for $functionAppName..." -ForegroundColor Cyan
$connectorExtensionKey = (az functionapp keys list -g $resourceGroupName -n $functionAppName --query "systemKeys.connector_extension" -o tsv)

function New-TriggerConfig {
    param(
        [Parameter(Mandatory)] [string] $FunctionName,
        [Parameter(Mandatory)] [string] $OperationName,
        [Parameter(Mandatory)] [string] $Description,
        [object[]] $Parameters = @()
    )

    $triggerName = "$connectorNamespaceConnectionName-$($FunctionName.ToLower())"
    $callbackUrl = "https://$functionAppName.azurewebsites.net/runtime/webhooks/connector?functionName=$FunctionName&code=$connectorExtensionKey"
    $parametersShorthand = "[" + (($Parameters | ForEach-Object { "{name:$($_.name),value:'$($_.value)'}" }) -join ",") + "]"
    $notifFile = Join-Path $PSScriptRoot ".notification-details-$([System.Guid]::NewGuid().ToString('N')).json"
    @{ callbackUrl = $callbackUrl } | ConvertTo-Json -Compress | Set-Content -Path $notifFile -NoNewline

    Write-Host "  Creating trigger: $FunctionName -> $OperationName" -ForegroundColor Cyan

    try {
        az connector-namespace trigger delete `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $triggerName --yes 2>$null | Out-Null

        az connector-namespace trigger create `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            -n $triggerName `
            --connection-details "{connectionName:$connectorNamespaceConnectionName,connectorName:teams}" `
            --operation-name $OperationName `
            --parameters $parametersShorthand `
            --notification-details "@$notifFile" `
            --description $Description `
            --metadata "{destinationType:functionApp,functionAppName:$functionAppName,functionAppResourceGroup:$resourceGroupName,functionAppSubscriptionId:$subscriptionId,functionName:$FunctionName,recurrenceFrequency:Minute,recurrenceInterval:'5'}" `
            -o none

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Failed to create trigger config for $FunctionName." -ForegroundColor Red
            exit 1
        }
    }
    finally {
        Remove-Item $notifFile -ErrorAction SilentlyContinue
    }
}

# --- Create trigger configs for all 4 functions ---
Write-Host "Creating Connector Namespace trigger configs..." -ForegroundColor Yellow

New-TriggerConfig `
    -FunctionName "OnNewChannelMessage" `
    -OperationName "OnNewChannelMessage" `
    -Description "When a new channel message is added" `
    -Parameters @(
        @{ name = "groupId"; value = $teamsGroupId }
        @{ name = "channelId"; value = $teamsChannelId }
    )

New-TriggerConfig `
    -FunctionName "OnNewChannelMessageMentioningMe" `
    -OperationName "OnNewChannelMessageMentioningMe" `
    -Description "When I am mentioned in a channel message" `
    -Parameters @(
        @{ name = "groupId"; value = $teamsGroupId }
        @{ name = "channelId"; value = $teamsChannelId }
    )

New-TriggerConfig `
    -FunctionName "OnGroupMembershipAdd" `
    -OperationName "OnGroupMembershipAdd" `
    -Description "When a new team member is added" `
    -Parameters @(
        @{ name = "groupId"; value = $teamsGroupId }
    )

New-TriggerConfig `
    -FunctionName "OnGroupMembershipRemoval" `
    -OperationName "OnGroupMembershipRemoval" `
    -Description "When a team member is removed" `
    -Parameters @(
        @{ name = "groupId"; value = $teamsGroupId }
    )

Write-Host "All trigger configs created." -ForegroundColor Green

Write-Host ""
Write-Host "Authorizing teams connection..." -ForegroundColor Yellow

$currentStatus = Get-ConnectionOverallStatus
if ($currentStatus -eq 'Connected') {
    Write-Host "Teams connection already Connected. Skipping consent." -ForegroundColor Green
}
else {
    Write-Host "-> A browser tab will open. Sign in with the Teams account you want to monitor." -ForegroundColor Cyan

    $consentLink = $null
    for ($attempt = 1; $attempt -le 5 -and -not $consentLink; $attempt++) {
        $consentLink = az connector-namespace connection list-consent-links `
            -g $resourceGroupName --namespace $connectorNamespaceName `
            --connection-name $connectorNamespaceConnectionName `
            --parameters "[{parameterName:token,redirectUrl:'https://portal.azure.com'}]" `
            --query "value[0].link" -o tsv 2>$null

        if (($LASTEXITCODE -ne 0 -or -not $consentLink) -and $attempt -lt 5) {
            Write-Host "Consent link not ready yet. Retrying in 5 seconds..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }

    if (-not $consentLink) {
        Write-Host "Failed to generate a consent URL for the Teams connection." -ForegroundColor Red
        exit 1
    }

    Write-Host "Consent URL: $consentLink" -ForegroundColor Cyan
    try {
        Start-Process $consentLink | Out-Null
    }
    catch {
        Write-Host "Could not open a browser automatically. Paste the consent URL into a browser manually." -ForegroundColor Yellow
    }
    Write-Host "If the browser did not open, paste this URL into a browser:" -ForegroundColor Yellow
    Write-Host $consentLink -ForegroundColor Cyan

    $deadline = (Get-Date).AddMinutes(5)
    $lastReportedStatus = $null
    $pollStatus = $currentStatus

    if ($currentStatus) {
        $lastReportedStatus = $currentStatus
        Write-Host "Connection status: $currentStatus" -ForegroundColor Cyan
    }

    while ((Get-Date) -lt $deadline) {
        $pollStatus = Get-ConnectionOverallStatus
        if ($pollStatus -and $pollStatus -ne $lastReportedStatus) {
            Write-Host "Connection status: $pollStatus" -ForegroundColor Cyan
            $lastReportedStatus = $pollStatus
        }

        if ($pollStatus -eq 'Connected') {
            Write-Host "Teams connection authorized." -ForegroundColor Green
            break
        }

        Start-Sleep -Seconds 3
    }

    if ($pollStatus -ne 'Connected') {
        Write-Host "Timed out waiting for the Teams connection to reach Connected status." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Done. All 4 Teams triggers are configured." -ForegroundColor Green
Write-Host "Tail logs: az functionapp log tail -g $resourceGroupName -n $functionAppName" -ForegroundColor Green
Write-Host ""