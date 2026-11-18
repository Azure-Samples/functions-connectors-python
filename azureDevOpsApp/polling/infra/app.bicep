targetScope = 'subscription'

param environmentName string
param location string
param resourceGroupName string
param functionAppName string
param storageName string
param insightsName string
param planName string
param namespaceName string
param connectionName string
@minLength(1)
param connectorPollingEndpoint string
@minLength(1)
param triggerConfigSettingsEncoded string
@allowed(['true', 'false'])
param functionAppExists string = 'false'

resource group 'Microsoft.Resources/resourceGroups@2024-03-01' existing = { name: resourceGroupName }
var existingAppSettings = functionAppExists == 'true'
  ? list('${resourceId(subscription().subscriptionId, resourceGroupName, 'Microsoft.Web/sites', functionAppName)}/config/appsettings', '2024-04-01').properties
  : {}

module app './app-resources.bicep' = {
  scope: group
  name: 'azuredevops-polling-app'
  params: {
    environmentName: environmentName
    location: location
    functionAppName: functionAppName
    storageName: storageName
    insightsName: insightsName
    planName: planName
    namespaceName: namespaceName
    connectionName: connectionName
    connectorPollingEndpoint: connectorPollingEndpoint
    triggerConfigSettingsEncoded: triggerConfigSettingsEncoded
    existingAppSettings: existingAppSettings
  }
}
output FUNCTION_APP_HOSTNAME string = app.outputs.hostname