targetScope = 'subscription'

param resourceGroupName string
param connectorNamespaceName string
param connectorNamespaceConnectionName string
@minLength(1)
param teamsGroupId string
@minLength(1)
param teamsChannelId string

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' existing = { name: resourceGroupName }

module pollTriggers './poll-triggers.bicep' = {
  scope: rg
  name: 'poll-triggers'
  params: {
    namespaceName: connectorNamespaceName
    connectionName: connectorNamespaceConnectionName
    teamsGroupId: teamsGroupId
    teamsChannelId: teamsChannelId
  }
}

output connectorPollingEndpoint string = pollTriggers.outputs.pollingEndpoint
output triggerConfigSettings object = pollTriggers.outputs.triggerConfigSettings
output triggerConfigSettingsEncoded string = base64(string(pollTriggers.outputs.triggerConfigSettings))
output teamsGroupId string = teamsGroupId
output teamsChannelId string = teamsChannelId
