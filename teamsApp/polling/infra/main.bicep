targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string

@metadata({ azd: { type: 'location' } })
param location string
param connectorNamespaceLocation string = 'westcentralus'
param telemetryLocation string = 'eastus2'

@metadata({ azd: { type: 'principalId' } })
param userPrincipalId string = deployer().objectId

metadata name = 'Azure Functions Teams Connector Polling (Python)'
metadata description = 'Teams events with Poll delivery on Python 3.14 Flex Consumption.'

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }
var functionAppName = 'func-${resourceToken}'
var deploymentStorageContainerName = 'app-package-${take(functionAppName, 32)}-${take(toLower(uniqueString(functionAppName, environmentName)), 7)}'
var storageBlobDataOwner = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageQueueDataContributor = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
var storageTableDataContributor = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
var monitoringMetricsPublisherRoleId = '3913510d-42f4-4e42-8a64-420c390055eb'

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.15.0' = {
  name: 'loganalytics'
  scope: rg
  params: {
    name: 'log-${resourceToken}-${telemetryLocation}'
    location: telemetryLocation
    tags: tags
    dataRetention: 30
  }
}

module monitoring 'br/public:avm/res/insights/component:0.7.1' = {
  name: 'appinsights'
  scope: rg
  params: {
    name: 'appi-${resourceToken}'
    location: telemetryLocation
    tags: tags
    workspaceResourceId: logAnalytics.outputs.resourceId
    disableLocalAuth: true
    roleAssignments: [
      {
        roleDefinitionIdOrName: monitoringMetricsPublisherRoleId
        principalId: userPrincipalId
        principalType: 'User'
      }
    ]
  }
}

module storageAccount 'br/public:avm/res/storage/storage-account:0.32.0' = {
  name: 'storage'
  scope: rg
  params: {
    name: 'st${resourceToken}'
    location: location
    tags: tags
    skuName: 'Standard_LRS'
    kind: 'StorageV2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Enabled'
    networkAcls: { defaultAction: 'Allow' }
    minimumTlsVersion: 'TLS1_2'
    blobServices: { containers: [{ name: deploymentStorageContainerName }] }
    roleAssignments: [
      {
        roleDefinitionIdOrName: storageBlobDataOwner
        principalId: userPrincipalId
        principalType: 'User'
      }
      {
        roleDefinitionIdOrName: storageQueueDataContributor
        principalId: userPrincipalId
        principalType: 'User'
      }
      {
        roleDefinitionIdOrName: storageTableDataContributor
        principalId: userPrincipalId
        principalType: 'User'
      }
    ]
  }
}

module functionAppPlan 'br/public:avm/res/web/serverfarm:0.7.0' = {
  name: 'function-plan'
  scope: rg
  params: {
    name: 'plan-${resourceToken}'
    location: location
    tags: tags
    skuName: 'FC1'
    reserved: true
  }
}

module connectorNamespace './connector-namespace.bicep' = {
  name: 'connector-namespace'
  scope: rg
  params: {
    name: 'cns-${resourceToken}'
    location: connectorNamespaceLocation
    tags: tags
    connectionName: 'cnsc-${resourceToken}'
    userPrincipalId: userPrincipalId
  }
}

output resourceGroupName string = rg.name
output functionAppName string = functionAppName
output functionAppPlanName string = functionAppPlan.outputs.name
output storageAccountName string = storageAccount.outputs.name
output appInsightsName string = monitoring.outputs.name
output connectorNamespaceName string = connectorNamespace.outputs.name
output connectorNamespaceConnectionName string = connectorNamespace.outputs.connectionName