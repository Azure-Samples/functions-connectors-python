targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string
@metadata({ azd: { type: 'location' } })
param location string
param connectorNamespaceLocation string = 'brazilsouth'
param applicationInsightsLocation string = ''
@metadata({ azd: { type: 'principalId' } })
param userPrincipalId string = deployer().objectId
param authenticationParameterSetName string = 'BasicAuthentication'

var token = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }
var functionName = 'func-${token}'
var containerName = 'app-package-${token}'
var storageRoles = [
  'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
]
resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}
module workspace 'br/public:avm/res/operational-insights/workspace:0.15.0' = {
  name: 'loganalytics'
  scope: rg
  params: { name: 'log-${token}', location: location, tags: tags, dataRetention: 30 }
}
module insights 'br/public:avm/res/insights/component:0.7.1' = {
  name: 'appinsights'
  scope: rg
  params: {
    name: 'appi-${token}'
    location: empty(applicationInsightsLocation) ? location : applicationInsightsLocation
    tags: tags
    workspaceResourceId: workspace.outputs.resourceId
    disableLocalAuth: true
    roleAssignments: [{
      roleDefinitionIdOrName: '3913510d-42f4-4e42-8a64-420c390055eb'
      principalId: userPrincipalId
      principalType: 'User'
    }]
  }
}
module storage 'br/public:avm/res/storage/storage-account:0.32.0' = {
  name: 'storage'
  scope: rg
  params: {
    name: 'st${token}'
    location: location
    tags: tags
    skuName: 'Standard_LRS'
    kind: 'StorageV2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow' }
    minimumTlsVersion: 'TLS1_2'
    blobServices: { containers: [{ name: containerName }] }
    roleAssignments: [for role in storageRoles: {
      roleDefinitionIdOrName: role
      principalId: userPrincipalId
      principalType: 'User'
    }]
  }
}
module plan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: 'plan'
  scope: rg
  params: { name: 'plan-${token}', location: location, tags: tags, skuName: 'FC1', reserved: true }
}
module connector './connector-namespace.bicep' = {
  name: 'connector-namespace'
  scope: rg
  params: {
    name: 'cns-${token}'
    location: connectorNamespaceLocation
    tags: tags
    connectionName: 'cnsc-${token}'
    userPrincipalId: userPrincipalId
    authenticationParameterSetName: authenticationParameterSetName
  }
}
// The postdeploy hook registers callbacks only after OAuth and host readiness checks.
module app 'br/public:avm/res/web/site:0.22.0' = {
  name: 'function-app'
  scope: rg
  params: {
    name: functionName
    location: location
    tags: union(tags, { 'azd-service-name': 'function-app' })
    kind: 'functionapp,linux'
    serverFarmResourceId: plan.outputs.resourceId
    httpsOnly: true
    managedIdentities: { systemAssigned: true }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.outputs.primaryBlobEndpoint}${containerName}'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 100, alwaysReady: [] }
      runtime: { name: 'python', version: '3.14' }
    }
    siteConfig: { minTlsVersion: '1.2' }
    configs: [{
      name: 'appsettings'
      properties: {
        AzureWebJobsStorage__credential: 'managedidentity'
        AzureWebJobsStorage__accountName: storage.outputs.name
        APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
        APPLICATIONINSIGHTS_CONNECTION_STRING: insights.outputs.connectionString
        ConnectorNamespace__credential: 'managedidentity'
        PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
        'AzureWebJobs.OnSalesforceNewItems.Disabled': 'true'
        'AzureWebJobs.OnSalesforceUpdatedItems.Disabled': 'true'
      }
    }]
  }
}
module access './function-access.bicep' = {
  name: 'function-access'
  scope: rg
  params: {
    functionAppPrincipalId: app.outputs.systemAssignedMIPrincipalId!
    storageAccountName: storage.outputs.name
    appInsightsName: insights.outputs.name
    connectorNamespaceName: connector.outputs.name
    connectorConnectionName: connector.outputs.connectionName
  }
}

output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output FUNCTION_APP_NAME string = app.outputs.name
output resourceGroupName string = rg.name
output functionAppName string = app.outputs.name
output functionAppDefaultHostname string = app.outputs.defaultHostname
output connectorNamespaceName string = connector.outputs.name
output connectorNamespaceResourceId string = connector.outputs.resourceId
output connectorNamespaceConnectionName string = connector.outputs.connectionName
output connectorNamespaceLocation string = connectorNamespaceLocation
output salesforceAuthenticationParameterSetName string = authenticationParameterSetName