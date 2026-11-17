param functionAppName string
param storageAccountName string
param appInsightsName string
param triggerConfigSettingsEncoded string
@secure()
param existingAppSettings object

resource insights 'Microsoft.Insights/components@2020-02-02' existing = { name: appInsightsName }
resource app 'Microsoft.Web/sites@2024-04-01' existing = { name: functionAppName }
resource settings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: app
  name: 'appsettings'
  properties: union(existingAppSettings, {
    AzureWebJobsStorage__credential: 'managedidentity'
    AzureWebJobsStorage__accountName: storageAccountName
    APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
    APPLICATIONINSIGHTS_CONNECTION_STRING: insights.properties.ConnectionString
    PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
    ConnectorNamespace__credential: 'managedidentity'
  }, json(base64ToString(triggerConfigSettingsEncoded)))
}