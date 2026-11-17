param environmentName string
param location string
param functionAppName string
param storageName string
param insightsName string
param planName string
param namespaceName string
param connectionName string
param connectorPollingEndpoint string
param triggerConfigSettingsEncoded string
@secure()
param existingAppSettings object

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageName }
resource plan 'Microsoft.Web/serverfarms@2024-04-01' existing = { name: planName }
resource app 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  tags: { 'azd-env-name': environmentName, 'azd-service-name': 'function-app' }
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}app-package'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      runtime: { name: 'python', version: '3.14' }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100, alwaysReady: [] }
    }
    siteConfig: { minTlsVersion: '1.2', ftpsState: 'Disabled' }
  }
}
module settings './app-settings.bicep' = {
  name: 'azuredevops-polling-settings'
  params: {
    functionAppName: app.name
    storageName: storageName
    insightsName: insightsName
    connectorPollingEndpoint: connectorPollingEndpoint
    triggerConfigSettingsEncoded: triggerConfigSettingsEncoded
    existingAppSettings: existingAppSettings
  }
}
module access './function-access.bicep' = {
  name: 'azuredevops-polling-access'
  params: {
    functionPrincipalId: app.identity.principalId
    storageName: storageName
    insightsName: insightsName
    namespaceName: namespaceName
    connectionName: connectionName
  }
}
output hostname string = app.properties.defaultHostName