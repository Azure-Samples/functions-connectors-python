param functionAppName string
param storageName string
param insightsName string
param connectorPollingEndpoint string
param triggerConfigSettingsEncoded string
@secure()
param existingAppSettings object

resource app 'Microsoft.Web/sites@2024-04-01' existing = { name: functionAppName }
resource insights 'Microsoft.Insights/components@2020-02-02' existing = { name: insightsName }
resource settings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: app
  name: 'appsettings'
  properties: union(existingAppSettings, {
    AzureWebJobsStorage__accountName: storageName
    AzureWebJobsStorage__credential: 'managedidentity'
    APPLICATIONINSIGHTS_CONNECTION_STRING: insights.properties.ConnectionString
    APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
    ConnectorNamespace__credential: 'managedidentity'
    ConnectorNamespace__pollingEndpoint: connectorPollingEndpoint
  }, json(base64ToString(triggerConfigSettingsEncoded)))
}