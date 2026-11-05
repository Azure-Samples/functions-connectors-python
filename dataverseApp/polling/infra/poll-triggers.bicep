param namespaceName string
param connectionName string
param functionAppName string
@minLength(1)
param environmentUrl string
param tableName string = 'account'
param enableSeparateRowTriggers bool = false
@minLength(1)
param entitySetName string = 'accounts'
param enableActionTrigger bool = false

var organization = endsWith(environmentUrl, '/') ? substring(environmentUrl, 0, length(environmentUrl) - 1) : environmentUrl
var destination = {
  destinationType: 'functionApp'
  functionAppName: functionAppName
  functionAppResourceGroup: resourceGroup().name
  functionAppSubscriptionId: subscription().subscriptionId
}
var separateTriggers = [
  { functionName: 'OnDataverseRowAdded', operationName: 'GetOnNewItems_V2' }
  { functionName: 'OnDataverseRowModified', operationName: 'GetOnUpdatedItems_V2' }
  { functionName: 'OnDataverseRowDeleted', operationName: 'GetOnDeletedItems_V2' }
]

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = {
  name: namespaceName
}

resource rowTrigger 'Microsoft.Web/connectorGateways/triggerConfigs@2026-05-01-preview' = {
  parent: connectorNamespace
  name: 'dataverse-ondataverserowchanged'
  properties: {
    connectionDetails: { connectionName: connectionName, connectorName: 'commondataservice' }
    deliveryMode: 'Poll'
    operationName: 'SubscribeWebhookTrigger'
    metadata: union(destination, { functionName: 'OnDataverseRowChanged' })
    parameters: [
      { name: 'organization', value: organization }
      { name: 'entityname', value: tableName }
      { name: 'message', value: '7' }
      { name: 'scope', value: '4' }
    ]
    state: 'Enabled'
    type: 'NotSpecified'
    description: 'Current Dataverse added, modified, or deleted operation with Poll delivery.'
  }
}

resource separateRowTriggers 'Microsoft.Web/connectorGateways/triggerConfigs@2026-05-01-preview' = [for trigger in separateTriggers: if (enableSeparateRowTriggers) {
  parent: connectorNamespace
  name: 'dataverse-${toLower(trigger.functionName)}'
  properties: {
    connectionDetails: { connectionName: connectionName, connectorName: 'commondataservice' }
    deliveryMode: 'Poll'
    operationName: trigger.operationName
    metadata: union(destination, { functionName: trigger.functionName })
    parameters: [
      { name: 'dataset', value: organization }
      { name: 'table', value: entitySetName }
    ]
    state: 'Enabled'
    type: 'NotSpecified'
  }
}]

var receiveUri = split(string(rowTrigger.properties.pollingEndpoints.receiveUri), '?')[0]
var endpointBase = substring(receiveUri, 0, indexOf(toLower(receiveUri), '/triggerconfigs/'))

output pollingEndpoint string = endsWith(toLower(endpointBase), '/api')
  ? substring(endpointBase, 0, max(0, length(endpointBase) - 4))
  : endpointBase

output triggerConfigSettings object = {
  OnDataverseRowChangedTriggerConfigName: rowTrigger.name
  OnDataverseActionPerformedTriggerConfigName: 'dataverse-ondataverseactionperformed'
  'AzureWebJobs.OnDataverseActionPerformed.Disabled': string(!enableActionTrigger)
  OnDataverseRowAddedTriggerConfigName: 'dataverse-ondataverserowadded'
  OnDataverseRowModifiedTriggerConfigName: 'dataverse-ondataverserowmodified'
  OnDataverseRowDeletedTriggerConfigName: 'dataverse-ondataverserowdeleted'
  'AzureWebJobs.OnDataverseRowAdded.Disabled': string(!enableSeparateRowTriggers)
  'AzureWebJobs.OnDataverseRowModified.Disabled': string(!enableSeparateRowTriggers)
  'AzureWebJobs.OnDataverseRowDeleted.Disabled': string(!enableSeparateRowTriggers)
}
