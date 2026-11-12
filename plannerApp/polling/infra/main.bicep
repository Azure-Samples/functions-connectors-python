targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string
@metadata({ azd: { type: 'location' } })
param location string
param connectorNamespaceLocation string = 'westcentralus'
param applicationInsightsLocation string = ''
@metadata({ azd: { type: 'principalId' } })
param userPrincipalId string = deployer().objectId

var token = toLower(uniqueString(subscription().id, environmentName, location, 'planner-polling'))
var tags = { 'azd-env-name': environmentName }
var appName = 'func-${token}'
var storageName = 'st${token}'
var namespaceName = 'cn-${token}'
var connectionName = 'planner-${token}'
var containerName = 'app-package-${token}'
var functions = ['OnPlannerCompleteTask', 'OnPlannerNewTask', 'OnPlannerTaskAssignedToMe']
var disabledSettings = toObject(functions, function => 'AzureWebJobs.${function}.Disabled', function => 'true')
var triggerNames = toObject(functions, function => '${function}TriggerConfigName', function => '${connectionName}-polling-${toLower(function)}')

resource group 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module workspace 'br/public:avm/res/operational-insights/workspace:0.15.0' = {
  name: 'workspace'
  scope: group
  params: { name: 'log-${token}', location: location, tags: tags, dataRetention: 30 }
}

module monitoring 'br/public:avm/res/insights/component:0.7.1' = {
  name: 'monitoring'
  scope: group
  params: {
    name: 'appi-${token}'
    location: empty(applicationInsightsLocation) ? location : applicationInsightsLocation
    tags: tags
    workspaceResourceId: workspace.outputs.resourceId
    disableLocalAuth: true
  }
}

module storage 'br/public:avm/res/storage/storage-account:0.32.0' = {
  name: 'storage'
  scope: group
  params: {
    name: storageName
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
    roleAssignments: [
      { roleDefinitionIdOrName: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b', principalId: userPrincipalId, principalType: 'User' }
      { roleDefinitionIdOrName: '974c5e8b-45b9-4653-ba55-5f855dd0fb88', principalId: userPrincipalId, principalType: 'User' }
      { roleDefinitionIdOrName: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3', principalId: userPrincipalId, principalType: 'User' }
    ]
  }
}

module plan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: 'plan'
  scope: group
  params: { name: 'plan-${token}', location: location, tags: tags, skuName: 'FC1', reserved: true }
}

module namespace './connector-namespace.bicep' = {
  name: 'namespace'
  scope: group
  params: {
    name: namespaceName
    location: connectorNamespaceLocation
    tags: tags
    connectionName: connectionName
    userPrincipalId: userPrincipalId
  }
}

// Disabled listeners have real future config names, but no invented service endpoint.
// The postdeploy hook registers Poll sources only after Planner OAuth is Connected.
module app 'br/public:avm/res/web/site:0.22.0' = {
  name: 'app'
  scope: group
  params: {
    name: appName
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
      properties: union({
        AzureWebJobsStorage__credential: 'managedidentity'
        AzureWebJobsStorage__accountName: storage.outputs.name
        AzureWebJobsStorage__blobServiceUri: storage.outputs.primaryBlobEndpoint
        AzureWebJobsStorage__queueServiceUri: 'https://${storage.outputs.name}.queue.${environment().suffixes.storage}'
        AzureWebJobsStorage__tableServiceUri: 'https://${storage.outputs.name}.table.${environment().suffixes.storage}'
        APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
        APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.connectionString
        PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
        ConnectorNamespace__credential: 'managedidentity'
      }, disabledSettings, triggerNames)
    }]
  }
}

module access './function-access.bicep' = {
  name: 'function-access'
  scope: group
  params: {
    functionAppPrincipalId: app.outputs.systemAssignedMIPrincipalId!
    storageAccountName: storage.outputs.name
    appInsightsName: monitoring.outputs.name
    connectorNamespaceName: namespace.outputs.name
    connectorConnectionName: namespace.outputs.connectionName
  }
}

output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output resourceGroupName string = group.name
output functionAppName string = app.outputs.name
output functionAppDefaultHostname string = app.outputs.defaultHostname
output connectorNamespaceName string = namespace.outputs.name
output connectorNamespaceConnectionName string = namespace.outputs.connectionName