targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string
@metadata({ azd: { type: 'location' } })
param location string
param connectorNamespaceLocation string = 'brazilsouth'
@metadata({ azd: { type: 'principalId' } })
param userPrincipalId string = deployer().objectId

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: { 'azd-env-name': environmentName }
}

module resources './resources.bicep' = {
  scope: resourceGroup
  name: 'vsts-polling-resources'
  params: {
    environmentName: environmentName
    location: location
    connectorNamespaceLocation: connectorNamespaceLocation
    userPrincipalId: userPrincipalId
  }
}

output resourceGroupName string = resourceGroup.name
output functionAppName string = resources.outputs.functionAppName
output FUNCTION_APP_HOSTNAME string = resources.outputs.functionAppHostname
output connectorNamespaceName string = resources.outputs.namespaceName
output connectorNamespaceResourceId string = resources.outputs.namespaceId
output connectorNamespaceConnectionName string = resources.outputs.connectionName
output CONNECTOR_NAMESPACE_LOCATION string = connectorNamespaceLocation
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output deliveryMode string = 'polling'