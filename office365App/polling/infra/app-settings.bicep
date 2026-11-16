param functionAppName string
param storageAccountName string
param appInsightsName string
param connectorPollingEndpoint string
param triggerConfigSettingsEncoded string
param sharedMailboxAddress string
@secure()
param existingAppSettings object

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}
resource monitoring 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}
resource functionApp 'Microsoft.Web/sites@2024-04-01' existing = {
  name: functionAppName
}

resource appSettings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: functionApp
  name: 'appsettings'
  properties: union(existingAppSettings, {
    AzureWebJobsStorage__credential: 'managedidentity'
    AzureWebJobsStorage__accountName: storageAccount.name
    APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
    APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.properties.ConnectionString
    PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
    ConnectorNamespace__credential: 'managedidentity'
    ConnectorNamespace__pollingEndpoint: connectorPollingEndpoint
    'AzureWebJobs.OnSharedMailboxNewEmail.Disabled': string(empty(sharedMailboxAddress))
  }, json(base64ToString(triggerConfigSettingsEncoded)))
}
