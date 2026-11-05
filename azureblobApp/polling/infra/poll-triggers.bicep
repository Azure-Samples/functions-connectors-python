param namespaceName string
param connectionName string
param monitoredStorageAccountName string
param monitoredContainerName string

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = {
  name: namespaceName
}

resource triggerConfig 'Microsoft.Web/connectorGateways/triggerConfigs@2026-05-01-preview' = {
  parent: connectorNamespace
  name: 'azureblob-onazureblobupdatedfile'
  properties: {
    connectionDetails: {
      connectionName: connectionName
      connectorName: 'azureblob'
    }
    deliveryMode: 'Poll'
    operationName: 'OnUpdatedFiles_V2'
    parameters: [
      { name: 'dataset', value: monitoredStorageAccountName }
      { name: 'folderId', value: base64('%2f${monitoredContainerName}') }
    ]
    state: 'Enabled'
    type: 'NotSpecified'
    description: 'Azure Blob OnAzureBlobUpdatedFile with Poll delivery.'
  }
}

// Use the service's receive URI, removing the trigger path and optional /api suffix.
var receiveUri = split(string(triggerConfig.properties.pollingEndpoints.receiveUri), '?')[0]
var endpointBase = substring(receiveUri, 0, indexOf(toLower(receiveUri), '/triggerconfigs/'))

output pollingEndpoint string = endsWith(toLower(endpointBase), '/api')
  ? substring(endpointBase, 0, max(0, length(endpointBase) - 4))
  : endpointBase

output triggerConfigSettings object = {
  OnAzureBlobUpdatedFileTriggerConfigName: triggerConfig.name
}