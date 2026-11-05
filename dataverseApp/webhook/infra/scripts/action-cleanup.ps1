. (Join-Path $PSScriptRoot 'local-settings.ps1')

function Get-DataverseActionContext {
    param($Outputs, [ValidateSet('Poll', 'Webhook')] [string] $Mode,
        [string] $TriggerName = '', [string] $FunctionName = 'OnDataverseActionPerformed')
    foreach ($name in @('AZURE_SUBSCRIPTION_ID', 'resourceGroupName', 'connectorNamespaceName',
        'connectorNamespaceConnectionName', 'functionAppName', 'dataverseEnvironmentUrl')) {
        if ([string]::IsNullOrWhiteSpace([string]$Outputs.$name)) { throw "Missing $name required to track Dataverse action cleanup." }
    }
    $organization = [uri]$Outputs.dataverseEnvironmentUrl
    if (-not $organization.IsAbsoluteUri -or $organization.Scheme -ne 'https' -or
        $organization.UserInfo -or $organization.Query -or $organization.Fragment -or $organization.AbsolutePath -ne '/') {
        throw 'Dataverse environment must be an HTTPS organization URL without credentials, path or query.'
    }
    if (-not $TriggerName) {
        $TriggerName = if ($Mode -eq 'Poll') { 'dataverse-ondataverseactionperformed' } else {
            "$($Outputs.connectorNamespaceConnectionName)-ondataverseactionperformed"
        }
    }
    if ($TriggerName -notmatch '^[A-Za-z0-9_-]+$' -or $FunctionName -notmatch '^[A-Za-z0-9_]+$') {
        throw 'Invalid Dataverse action trigger or function name.'
    }
    $resourceGroup = "/subscriptions/$($Outputs.AZURE_SUBSCRIPTION_ID)/resourceGroups/$($Outputs.resourceGroupName)"
    return [ordered]@{
        schemaVersion = 1
        namespaceId = "$resourceGroup/providers/Microsoft.Web/connectorGateways/$($Outputs.connectorNamespaceName)"
        connectionName = [string]$Outputs.connectorNamespaceConnectionName
        appId = "$resourceGroup/providers/Microsoft.Web/sites/$($Outputs.functionAppName)"
        organization = $organization.AbsoluteUri.TrimEnd('/')
        mode = $Mode; triggerName = $TriggerName; operationName = 'BusinessEventsTrigger'; functionName = $FunctionName
    }
}

function Assert-DataverseActionContext {
    param($Expected, $Actual)
    if ($null -eq $Actual -or @($Actual.Keys).Count -ne @($Expected.Keys).Count) {
        throw 'Dataverse action cleanup context is invalid; preserve the journal for manual investigation.'
    }
    foreach ($name in $Expected.Keys) {
        if ([string]$Expected[$name] -cne [string]$Actual[$name]) {
            throw "Dataverse action cleanup context differs at '$name'; refusing to adopt or delete a registration."
        }
    }
}

function Get-DataverseActionJournal {
    param([string] $SampleRoot, $Context)
    $directory = Join-Path $SampleRoot '.azure'
    if (Test-Path -LiteralPath $directory) {
        $item = Get-Item -LiteralPath $directory -Force
        if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw '.azure must be a regular directory for Dataverse cleanup tracking.'
        }
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes("$($Context.namespaceId)|$($Context.connectionName)|$($Context.appId)|$($Context.mode)")
    $hash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
    return Join-Path $directory "dataverse-action-cleanup-$hash.json"
}

function Assert-DataverseDestination {
    param($Context, $Config, $Outputs, [string] $OperationName, [string] $FunctionName)
    $properties = $Config.properties
    $destination = $properties.metadata
    if ($Config.id -ine "$($Context.namespaceId)/triggerConfigs/$($Config.name)" -or
        $properties.operationName -cne $OperationName -or
        $properties.connectionDetails.connectionName -cne $Context.connectionName -or
        $properties.connectionDetails.connectorName -cne 'commondataservice' -or
        $destination.destinationType -cne 'functionApp' -or
        $destination.functionAppName -ine $Outputs.functionAppName -or
        $destination.functionAppResourceGroup -ine $Outputs.resourceGroupName -or
        $destination.functionAppSubscriptionId -ine $Outputs.AZURE_SUBSCRIPTION_ID -or
        $destination.functionName -cne $FunctionName) {
        throw 'Refusing to change Dataverse configuration with a different source or destination binding.'
    }
    if ($Context.mode -eq 'Poll') {
        if ($properties.deliveryMode -cne 'Poll') { throw 'Dataverse delivery mode differs.' }
    } else {
        if ([string]$properties.deliveryMode -cnotin @('', 'NotSpecified', 'Push')) { throw 'Dataverse delivery mode differs.' }
        $callback = [uri]$properties.notificationDetails.callbackUrl
        if ([string]::IsNullOrWhiteSpace([string]$Outputs.functionAppDefaultHostname) -or
            -not $callback.IsAbsoluteUri -or $callback.Scheme -ne 'https' -or $callback.Port -ne 443 -or
            $callback.Host -ine $Outputs.functionAppDefaultHostname -or
            $callback.AbsolutePath -cne '/runtime/webhooks/connector' -or
            $callback.Query -cnotin @("?functionName=$FunctionName", '?functionName=*sanitized*') -or
            $callback.UserInfo -or $callback.Fragment) {
            throw 'Refusing Dataverse cleanup for another application callback.'
        }
    }
}

function Protect-DataverseActionRegistration {
    [CmdletBinding()]
    param($Context, [string] $JournalPath, $Config, $Outputs, [switch] $BeforeCreate)
    $selectors = [ordered]@{}
    if ($null -ne $Config) {
        if ($Config.name -cne $Context.triggerName) { throw 'Dataverse action configuration name differs.' }
        Assert-DataverseDestination $Context $Config $Outputs $Context.operationName $Context.functionName
        if (@($Config.properties.parameters).Count -ne 5) { throw 'Unexpected Dataverse action parameters.' }
        foreach ($name in @('organization', 'catalog', 'category', 'entityname', 'sdkmessagename')) {
            $values = @($Config.properties.parameters | Where-Object name -CEQ $name)
            if ($values.Count -ne 1 -or [string]::IsNullOrWhiteSpace([string]$values[0].value)) {
                throw "Dataverse action configuration has missing or ambiguous '$name'."
            }
            $selectors[$name] = [string]$values[0].value
        }
        if ($selectors.organization.TrimEnd('/') -cne $Context.organization) { throw 'Dataverse source organization differs.' }
    } elseif ($BeforeCreate) {
        $selectors.organization = $Context.organization
        foreach ($pair in @(@('catalog', 'eventCatalog'), @('category', 'eventCategory'),
            @('entityname', 'eventTable'), @('sdkmessagename', 'eventAction'))) {
            $value = [string]$Outputs.($pair[1])
            if ([string]::IsNullOrWhiteSpace($value)) { throw "Missing action selector $($pair[1])." }
            $selectors[$pair[0]] = $value
        }
    }
    if (Test-Path -LiteralPath $JournalPath) {
        $item = Get-Item -LiteralPath $JournalPath -Force
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Dataverse action cleanup journal must be a regular file.'
        }
        $journal = Get-Content -LiteralPath $JournalPath -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
        Assert-DataverseActionContext $Context $journal.context
        if ($journal.status -cne 'SourceCleanupUnverified') { throw 'Invalid Dataverse action cleanup journal status.' }
        if ($null -eq $Config) {
            if ($BeforeCreate) { throw 'Dataverse action source cleanup remains unverified; preserve the journal before creating a replacement.' }
            return
        }
        Assert-DataverseActionContext $selectors $journal.selectors
        return
    }
    if ($null -eq $Config -and -not $BeforeCreate) {
        Write-Warning 'No action CN configuration or cleanup journal was found. Historical Dataverse source callback cleanup is not verified; see README Action subscription cleanup.'
        return
    }
    [IO.Directory]::CreateDirectory((Split-Path $JournalPath)) | Out-Null
    Write-PrivateJson $JournalPath (@{ context = $Context; selectors = $selectors; status = 'SourceCleanupUnverified' } | ConvertTo-Json -Depth 5)
}

function Assert-DataverseActionSourceCleanup {
    param([string] $JournalPath)
    if (Test-Path -LiteralPath $JournalPath) {
        throw "Only the Connector Namespace action configuration was removed. Dataverse source cleanup remains unverified. Follow README 'Action subscription cleanup'; preserve '$JournalPath' until exact owned callback cleanup and GET 404 are confirmed. No Dataverse callback was automatically deleted."
    }
}