function Get-DataverseSeparateRowTriggers {
    @(
        @{ functionName = 'OnDataverseRowAdded'; operationName = 'SubscribeOnNewItems' }
        @{ functionName = 'OnDataverseRowModified'; operationName = 'SubscribeOnUpdatedItems' }
        @{ functionName = 'OnDataverseRowDeleted'; operationName = 'SubscribeOnDeletedItems' }
    )
}

function Get-DataverseRowParameters {
    param($Outputs)
    foreach ($name in @('dataverseEnvironmentUrl', 'dataverseEntitySetName', 'dataverseRowScope')) {
        if ([string]::IsNullOrWhiteSpace([string]$Outputs.$name)) {
            throw "Missing $name for separate row subscriptions. Select dataset/table via GetTables and scope via GetScopeFilters; run azd provision again."
        }
    }
    @(
        @{ name = 'dataset'; value = $Outputs.dataverseEnvironmentUrl.TrimEnd('/') }
        @{ name = 'table'; value = $Outputs.dataverseEntitySetName }
        @{ name = 'scope'; value = $Outputs.dataverseRowScope }
    )
}

function Assert-DataverseRowConfig {
    param($Config, $Trigger, $Outputs, [ValidateSet('Poll', 'Webhook')] [string] $Mode)
    $name = if ($Mode -eq 'Poll') {
        "dataverse-$($Trigger.functionName.ToLowerInvariant())"
    } else {
        "$($Outputs.connectorNamespaceConnectionName)-$($Trigger.functionName.ToLowerInvariant())"
    }
    $namespaceId = "/subscriptions/$($Outputs.AZURE_SUBSCRIPTION_ID)/resourceGroups/$($Outputs.resourceGroupName)/providers/Microsoft.Web/connectorGateways/$($Outputs.connectorNamespaceName)"
    $properties = $Config.properties
    $destination = $properties.metadata
    if ($Config.name -cne $name -or $Config.id -ine "$namespaceId/triggerConfigs/$name" -or
        $properties.operationName -cne $Trigger.operationName -or
        $properties.connectionDetails.connectionName -cne $Outputs.connectorNamespaceConnectionName -or
        $properties.connectionDetails.connectorName -cne 'commondataservice' -or
        $destination.destinationType -cne 'functionApp' -or
        $destination.functionAppName -ine $Outputs.functionAppName -or
        $destination.functionAppResourceGroup -ine $Outputs.resourceGroupName -or
        $destination.functionAppSubscriptionId -ine $Outputs.AZURE_SUBSCRIPTION_ID -or
        $destination.functionName -cne $Trigger.functionName) {
        throw "Refusing to change Dataverse row configuration '$name' with a different operation or binding. Legacy GetOn*_V2 configurations require explicit source cleanup and removal, or a fresh environment; they cannot be migrated in place."
    }
    if (($Mode -eq 'Poll' -and $properties.deliveryMode -cne 'Poll') -or
        ($Mode -eq 'Webhook' -and $properties.deliveryMode -cnotin @($null, '', 'Webhook', 'Push', 'NotSpecified'))) {
        throw "Dataverse row delivery mode differs for '$name'."
    }
    if ($Mode -eq 'Webhook') {
        $callback = $null
        if (-not [uri]::TryCreate([string]$properties.notificationDetails.callbackUrl, [UriKind]::Absolute, [ref]$callback) -or
            [string]::IsNullOrWhiteSpace([string]$Outputs.functionAppDefaultHostname) -or
            $callback.Scheme -ne 'https' -or $callback.Port -ne 443 -or
            $callback.Host -ine $Outputs.functionAppDefaultHostname -or
            $callback.AbsolutePath -cne '/runtime/webhooks/connector' -or
            $callback.Query -cnotin @("?functionName=$($Trigger.functionName)", '?functionName=*sanitized*') -or
            $callback.UserInfo -or $callback.Fragment) {
            throw "Dataverse row callback differs for '$name'."
        }
    }
    $selectors = @{}
    if (@($properties.parameters).Count -ne 3) { throw "Unexpected Dataverse row selectors for '$name'." }
    foreach ($parameter in $properties.parameters) {
        if ($parameter.name -cnotin @('dataset', 'table', 'scope') -or
            $selectors.ContainsKey($parameter.name) -or [string]::IsNullOrWhiteSpace([string]$parameter.value)) {
            throw "Missing or ambiguous Dataverse row selector for '$name'."
        }
        $selectors[$parameter.name] = [string]$parameter.value
    }
    if ($selectors.dataset -cne $Outputs.dataverseEnvironmentUrl.TrimEnd('/') -or
        $selectors.table -cne $Outputs.dataverseEntitySetName -or
        (-not [string]::IsNullOrWhiteSpace([string]$Outputs.dataverseRowScope) -and
            $selectors.scope -cne $Outputs.dataverseRowScope)) {
        throw "Dataverse row selectors differ for '$name'; existing subscriptions were not replaced."
    }
}
