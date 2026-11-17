param functionAppName string
param storageAccountName string
param appInsightsName string
param listenerSettings object
@secure()
param existingAppSettings object

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageAccountName }
resource monitoring 'Microsoft.Insights/components@2020-02-02' existing = { name: appInsightsName }
resource app 'Microsoft.Web/sites@2024-04-01' existing = { name: functionAppName }
resource settings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: app
  name: 'appsettings'
  properties: union(existingAppSettings, {
    AzureWebJobsStorage__credential: 'managedidentity'
    AzureWebJobsStorage__accountName: storage.name
    AzureWebJobsStorage__blobServiceUri: storage.properties.primaryEndpoints.blob
    AzureWebJobsStorage__queueServiceUri: 'https://${storage.name}.queue.${environment().suffixes.storage}'
    AzureWebJobsStorage__tableServiceUri: 'https://${storage.name}.table.${environment().suffixes.storage}'
    APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
    APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.properties.ConnectionString
    PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
    ConnectorNamespace__credential: 'managedidentity'
  }, listenerSettings)
}