param namespaceName string
param connectionName string

@minLength(1)
@description('OneDrive connector folder identifier, not a display path. Passed unchanged to the connector.')
param folderId string = 'root'

var triggers = [
  {
    functionName: 'OnOneDriveNewFile'
    operationName: 'OnNewFilesV2'
  }
  {
    functionName: 'OnOneDriveUpdatedFile'
    operationName: 'OnUpdatedFilesV2'
  }
  {
    functionName: 'OnOneDriveNewFileContent'
    operationName: 'OnNewFileV2'
  }
  {
    functionName: 'OnOneDriveUpdatedFileContent'
    operationName: 'OnUpdatedFileV2'
  }
]

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = {
  name: namespaceName
}

resource triggerConfigs 'Microsoft.Web/connectorGateways/triggerConfigs@2026-05-01-preview' = [for trigger in triggers: {
  parent: connectorNamespace
  name: 'onedrive-${toLower(trigger.functionName)}'
  properties: {
    connectionDetails: {
      connectionName: connectionName
      connectorName: 'onedriveforbusiness'
    }
    deliveryMode: 'Poll'
    operationName: trigger.operationName
    parameters: [
      { name: 'folderId', value: folderId }
    ]
    state: 'Enabled'
    type: 'NotSpecified'
    description: 'OneDrive ${trigger.functionName} with Poll delivery.'
  }
}]

// Keep the service host and gateway path; remove the trigger path and optional /api suffix.
var receiveUri = split(string(triggerConfigs[0].properties.pollingEndpoints.receiveUri), '?')[0]
var endpointBase = substring(receiveUri, 0, indexOf(toLower(receiveUri), '/triggerconfigs/'))

output pollingEndpoint string = endsWith(toLower(endpointBase), '/api')
  ? substring(endpointBase, 0, max(0, length(endpointBase) - 4))
  : endpointBase

output triggerConfigSettings object = toObject(
  triggers,
  trigger => '${trigger.functionName}TriggerConfigName',
  trigger => 'onedrive-${toLower(trigger.functionName)}'
)