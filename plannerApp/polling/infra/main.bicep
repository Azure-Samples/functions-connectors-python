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

output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output resourceGroupName string = group.name
output functionAppName string = appName
output functionAppPlanName string = plan.outputs.name
output storageAccountName string = storage.outputs.name
output appInsightsName string = monitoring.outputs.name
output deploymentStorageContainerName string = containerName
output connectorNamespaceName string = namespace.outputs.name
output connectorNamespaceConnectionName string = namespace.outputs.connectionName