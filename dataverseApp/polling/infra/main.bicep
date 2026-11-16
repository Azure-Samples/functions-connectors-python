targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Environment name used to generate resource names.')
param environmentName string

@metadata({ azd: { type: 'location' } })
@description('Location for all resources except the Connector Namespace and optional telemetry override.')
param location string

param telemetryLocation string = ''
param connectorNamespaceLocation string = 'westcentralus'

@minLength(1)
@description('Required Dataverse organization URL, for example https://contoso.crm.dynamics.com.')
param dataverseEnvironmentUrl string

@description('Logical table name, for example account, not the accounts entity set.')
param dataverseTableName string = 'account'
@description('Table Name selector returned by GetTables for the selected environment.')
param dataverseEntitySetName string = ''
@description('Exact GetScopeFilters selector for the selected environment and table.')
param dataverseRowScope string = ''
param eventCatalog string = ''
param eventCategory string = ''
param eventTable string = ''
param eventAction string = ''

@metadata({ azd: { type: 'principalId' } })
param userPrincipalId string = deployer().objectId

metadata name = 'Azure Functions Microsoft Dataverse Poll Delivery (Python)'
metadata description = 'Dataverse row changes and action-performed events with Poll delivery.'

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }
var effectiveTelemetryLocation = empty(telemetryLocation) ? location : telemetryLocation
var functionAppName = '${abbrs.webSitesFunctions}${resourceToken}'
var functionAppPlanName = '${abbrs.webServerFarms}${resourceToken}'
var resourceGroupName = '${abbrs.resourcesResourceGroups}${environmentName}'
var storageAccountName = '${abbrs.storageStorageAccounts}${resourceToken}'
var logAnalyticsName = '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
var appInsightsName = '${abbrs.insightsComponents}${resourceToken}'
var connectorNamespaceName = '${abbrs.connectorNamespaces}${resourceToken}'
var connectorNamespaceConnectionName = '${abbrs.connectorNamespacesConnections}${resourceToken}'
var deploymentStorageContainerName = 'app-package-${take(functionAppName, 32)}-${take(toLower(uniqueString(functionAppName, environmentName)), 7)}'
var storageBlobDataOwner = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageQueueDataContributor = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
var storageTableDataContributor = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
var monitoringMetricsPublisherRoleId = '3913510d-42f4-4e42-8a64-420c390055eb'

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.15.0' = {
  name: '${uniqueString(deployment().name, location)}-loganalytics'
  scope: rg
  params: {
    name: logAnalyticsName
    location: effectiveTelemetryLocation
    tags: tags
    dataRetention: 30
  }
}

module monitoring 'br/public:avm/res/insights/component:0.7.1' = {
  name: '${uniqueString(deployment().name, location)}-appinsights'
  scope: rg
  params: {
    name: appInsightsName
    location: effectiveTelemetryLocation
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
  scope: rg
  name: storageAccountName
  params: {
    name: storageAccountName
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
  scope: rg
  name: functionAppPlanName
  params: {
    name: functionAppPlanName
    location: location
    tags: tags
    skuName: 'FC1'
    reserved: true
  }
}

module connectorNamespace './connector-namespace.bicep' = {
  scope: rg
  name: connectorNamespaceName
  params: {
    name: connectorNamespaceName
    location: connectorNamespaceLocation
    tags: tags
    connectionName: connectorNamespaceConnectionName
    userPrincipalId: userPrincipalId
  }
}

output resourceGroupResourceId string = rg.id
output resourceGroupName string = rg.name
output functionAppName string = functionAppName
output functionAppPlanName string = functionAppPlan.outputs.name
output storageAccountName string = storageAccount.outputs.name
output appInsightsName string = monitoring.outputs.name
output connectorNamespaceName string = connectorNamespace.outputs.name
output connectorNamespaceConnectionName string = connectorNamespace.outputs.connectionName
output dataverseFunctionName string = 'OnDataverseRowChanged'
output dataverseEnvironmentUrl string = dataverseEnvironmentUrl
output dataverseTableName string = dataverseTableName
output dataverseEntitySetName string = dataverseEntitySetName
output dataverseRowScope string = dataverseRowScope
output eventCatalog string = eventCatalog
output eventCategory string = eventCategory
output eventTable string = eventTable
output eventAction string = eventAction
