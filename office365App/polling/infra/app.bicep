targetScope = 'subscription'

param environmentName string
param location string
param resourceGroupName string
param functionAppName string
param functionAppPlanName string
param storageAccountName string
param appInsightsName string
param connectorNamespaceName string
param connectorNamespaceConnectionName string
param sharedMailboxAddress string = ''
@minLength(1)
param connectorPollingEndpoint string
@minLength(1)
param triggerConfigSettingsEncoded string
@allowed(['true', 'false'])
param functionAppExists string = 'false'

var tags = { 'azd-env-name': environmentName }
var deploymentStorageContainerName = 'app-package-${take(functionAppName, 32)}-${take(toLower(uniqueString(functionAppName, environmentName)), 7)}'

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' existing = {
  name: resourceGroupName
}
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  scope: rg
  name: storageAccountName
}
resource monitoring 'Microsoft.Insights/components@2020-02-02' existing = {
  scope: rg
  name: appInsightsName
}
resource functionAppPlan 'Microsoft.Web/serverfarms@2024-04-01' existing = {
  scope: rg
  name: functionAppPlanName
}

var existingAppSettings = functionAppExists == 'true'
  ? list('${resourceId(subscription().subscriptionId, resourceGroupName, 'Microsoft.Web/sites', functionAppName)}/config/appsettings', '2024-04-01').properties
  : {}

module functionApp 'br/public:avm/res/web/site:0.22.0' = {
  scope: rg
  name: functionAppName
  params: {
    name: functionAppName
    location: location
    tags: union(tags, { 'azd-service-name': 'function-app' })
    kind: 'functionapp,linux'
    serverFarmResourceId: functionAppPlan.id
    httpsOnly: true
    managedIdentities: { systemAssigned: true }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.properties.primaryEndpoints.blob}${deploymentStorageContainerName}'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      scaleAndConcurrency: {
        instanceMemoryMB: 2048
        maximumInstanceCount: 100
        alwaysReady: []
      }
      runtime: { name: 'python', version: '3.14' }
    }
    siteConfig: { minTlsVersion: '1.2' }
  }
}

module appSettings './app-settings.bicep' = {
  scope: rg
  name: '${functionAppName}-settings'
  params: {
    functionAppName: functionAppName
    storageAccountName: storageAccountName
    appInsightsName: appInsightsName
    connectorPollingEndpoint: connectorPollingEndpoint
    triggerConfigSettingsEncoded: triggerConfigSettingsEncoded
    existingAppSettings: existingAppSettings
    sharedMailboxAddress: sharedMailboxAddress
  }
  dependsOn: [functionApp]
}

module functionAccess './function-access.bicep' = {
  name: 'function-access'
  scope: rg
  params: {
    functionAppPrincipalId: functionApp.outputs.systemAssignedMIPrincipalId!
    storageAccountName: storageAccount.name
    appInsightsName: monitoring.name
    connectorNamespaceName: connectorNamespaceName
    connectorConnectionName: connectorNamespaceConnectionName
  }
}

output functionAppDefaultHostname string = functionApp.outputs.defaultHostname
