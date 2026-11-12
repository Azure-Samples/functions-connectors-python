param environmentName string
param location string
param connectorNamespaceLocation string
param userPrincipalId string

var token = toLower(uniqueString(subscription().id, environmentName, location, 'vsts-webhook'))
var tags = { 'azd-env-name': environmentName }
var functions = [
  'OnVstsBuildCompleted'
  'OnVstsGitPullClosed'
  'OnVstsGitPullCreated'
  'OnVstsGitPush'
  'OnVstsTfvcCheckIn'
  'OnVstsWorkItemAssigned'
  'OnVstsWorkItemClosed'
  'OnVstsWorkItemCreated'
  'OnVstsWorkItemUpdated'
]
var storageRoles = [
  'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
]
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${token}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
  }
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}
resource package 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'app-package'
}
resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${token}'
  location: location
  tags: tags
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${token}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    DisableLocalAuth: true
  }
}
resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'plan-${token}'
  location: location
  tags: tags
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}
module namespace './namespace.bicep' = {
  name: 'namespace-${token}'
  params: {
    name: 'cn${token}'
    connectionName: 'vsts-${token}-entra'
    location: connectorNamespaceLocation
    userPrincipalId: userPrincipalId
    tags: tags
  }
}
resource app 'Microsoft.Web/sites@2024-04-01' = {
  name: 'func-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'function-app' })
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${package.name}'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      runtime: { name: 'python', version: '3.14' }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100, alwaysReady: [] }
    }
    siteConfig: { minTlsVersion: '1.2', ftpsState: 'Disabled' }
  }
}
resource settings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: app
  name: 'appsettings'
  properties: union({
    AzureWebJobsStorage__accountName: storage.name
    AzureWebJobsStorage__credential: 'managedidentity'
    APPLICATIONINSIGHTS_CONNECTION_STRING: insights.properties.ConnectionString
    APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
    PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
    VstsConnection: namespace.outputs.connectionRuntimeUrl
  }, toObject(functions, function => 'AzureWebJobs.${function}.Disabled', function => 'true'))
}
resource developerStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in storageRoles: {
  scope: storage
  name: guid(storage.id, userPrincipalId, role)
  properties: {
    principalId: userPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
  }
}]
resource developerMonitoring 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: insights
  name: guid(insights.id, userPrincipalId, '3913510d-42f4-4e42-8a64-420c390055eb')
  properties: {
    principalId: userPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
  }
}
module functionAccess './function-access.bicep' = {
  name: 'function-access-${token}'
  params: {
    functionPrincipalId: app.identity.principalId
    storageName: storage.name
    insightsName: insights.name
    namespaceName: namespace.outputs.name
    connectionName: namespace.outputs.connectionName
  }
}
output functionAppName string = app.name
output functionAppHostname string = app.properties.defaultHostName
output namespaceName string = namespace.outputs.name
output namespaceId string = namespace.outputs.resourceId
output connectionName string = namespace.outputs.connectionName