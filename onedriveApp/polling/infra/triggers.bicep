targetScope = 'subscription'

// Provisioned by the triggers layer after its preprovision hook authorizes the OAuth connection.
param resourceGroupName string
param connectorNamespaceName string
param connectorNamespaceConnectionName string

@minLength(1)
@description('OneDrive connector folder identifier, not a display path.')
param folderId string

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' existing = {
  name: resourceGroupName
}

module pollTriggers './poll-triggers.bicep' = {
  scope: rg
  name: 'poll-triggers'
  params: {
    namespaceName: connectorNamespaceName
    connectionName: connectorNamespaceConnectionName
    folderId: folderId
  }
}

@description('Base endpoint for receiving and acknowledging connector events.')
output connectorPollingEndpoint string = pollTriggers.outputs.pollingEndpoint

@description('Trigger config names used by the polling decorators.')
output triggerConfigSettings object = pollTriggers.outputs.triggerConfigSettings

@description('Trigger settings encoded for safe transfer through azd parameters.')
output triggerConfigSettingsEncoded string = base64(string(pollTriggers.outputs.triggerConfigSettings))
