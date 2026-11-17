targetScope = 'subscription'

param environmentName string
param location string
param resourceGroupName string
param functionAppName string
param functionAppPlanName string
param storageAccountName string
param appInsightsName string
param deploymentStorageContainerName string
param connectorNamespaceName string
param connectorNamespaceConnectionName string
@minLength(1)
param connectorPollingEndpoint string
@minLength(1)
param triggerConfigSettingsEncoded string
@allowed(['true', 'false'])
param functionAppExists string = 'false'

var tags = { 'azd-env-name': environmentName }
var existingAppSettings = functionAppExists == 'true'
  ? list('${resourceId(subscription().subscriptionId, resourceGroupName, 'Microsoft.Web/sites', functionAppName)}/config/appsettings', '2024-04-01').properties
  : {}

resource group 'Microsoft.Resources/resourceGroups@2025-04-01' existing = { name: resourceGroupName }
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  scope: group
  name: storageAccountName
}
resource plan 'Microsoft.Web/serverfarms@2024-04-01' existing = {
  scope: group
  name: functionAppPlanName
}

module app 'br/public:avm/res/web/site:0.22.0' = {
  name: functionAppName
  scope: group
  params: {
    name: functionAppName
    location: location
    tags: union(tags, { 'azd-service-name': 'function-app' })
    kind: 'functionapp,linux'
    serverFarmResourceId: plan.id
    httpsOnly: true
    managedIdentities: { systemAssigned: true }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${deploymentStorageContainerName}'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100, alwaysReady: [] }
      runtime: { name: 'python', version: '3.14' }
    }
    siteConfig: { minTlsVersion: '1.2' }
  }
}

module settings './app-settings.bicep' = {
  name: '${functionAppName}-settings'
  scope: group
  params: {
    functionAppName: functionAppName
    storageAccountName: storageAccountName
    appInsightsName: appInsightsName
    connectorPollingEndpoint: connectorPollingEndpoint
    triggerConfigSettingsEncoded: triggerConfigSettingsEncoded
    existingAppSettings: existingAppSettings
  }
  dependsOn: [app]
}

module access './function-access.bicep' = {
  name: 'function-access'
  scope: group
  params: {
    functionAppPrincipalId: app.outputs.systemAssignedMIPrincipalId!
    storageAccountName: storageAccountName
    appInsightsName: appInsightsName
    connectorNamespaceName: connectorNamespaceName
    connectorConnectionName: connectorNamespaceConnectionName
  }
}

output functionAppDefaultHostname string = app.outputs.defaultHostname