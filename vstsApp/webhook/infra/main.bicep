targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string
@metadata({ azd: { type: 'location' } })
param location string
param connectorNamespaceLocation string = 'brazilsouth'
@metadata({ azd: { type: 'principalId' } })
param userPrincipalId string = deployer().objectId
@allowed(['true', 'false'])
param functionAppExists string = 'false'

var appName = 'func-${toLower(uniqueString(subscription().id, environmentName, location, 'vsts-webhook'))}'
var existingAppSettings = functionAppExists == 'true'
  ? list('${resourceId(subscription().subscriptionId, 'rg-${environmentName}', 'Microsoft.Web/sites', appName)}/config/appsettings', '2024-04-01').properties
  : {}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: { 'azd-env-name': environmentName }
}
module resources './resources.bicep' = {
  scope: resourceGroup
  name: 'vsts-webhook-resources'
  params: {
    environmentName: environmentName
    location: location
    connectorNamespaceLocation: connectorNamespaceLocation
    userPrincipalId: userPrincipalId
    existingAppSettings: existingAppSettings
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
output deliveryMode string = 'webhook'