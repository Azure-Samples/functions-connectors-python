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
param enableSeparateRowTriggers bool = false
@minLength(1)
param dataverseEntitySetName string = 'accounts'
param enableActionTrigger bool = false
param eventCatalog string = ''
param eventCategory string = ''
param eventTable string = ''
param eventAction string = ''

@metadata({ azd: { type: 'principalId' } })
param userPrincipalId string = deployer().objectId

metadata name = 'Azure Functions Microsoft Dataverse Poll Delivery (Python)'
metadata description = 'Current Dataverse row changes and optional action-performed events with Poll delivery.'

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

module pollTriggers './poll-triggers.bicep' = {
  scope: rg
  name: '${connectorNamespaceName}-poll-triggers'
  params: {
    functionAppName: functionAppName
    namespaceName: connectorNamespace.outputs.name
    connectionName: connectorNamespace.outputs.connectionName
    environmentUrl: dataverseEnvironmentUrl
    tableName: dataverseTableName
    enableSeparateRowTriggers: enableSeparateRowTriggers
    entitySetName: dataverseEntitySetName
    enableActionTrigger: enableActionTrigger
    eventCatalog: eventCatalog
    eventCategory: eventCategory
    eventTable: eventTable
    eventAction: eventAction
  }
}

var allAppSettings = union({
  PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
  AzureWebJobsStorage__credential: 'managedidentity'
  AzureWebJobsStorage__accountName: storageAccount.outputs.name
  APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
  APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.connectionString
  ConnectorNamespace__credential: 'managedidentity'
  ConnectorNamespace__pollingEndpoint: pollTriggers.outputs.pollingEndpoint
}, pollTriggers.outputs.triggerConfigSettings)

module functionApp 'br/public:avm/res/web/site:0.22.0' = {
  scope: rg
  name: functionAppName
  params: {
    name: functionAppName
    location: location
    tags: union(tags, { 'azd-service-name': 'function-app' })
    kind: 'functionapp,linux'
    serverFarmResourceId: functionAppPlan.outputs.resourceId
    httpsOnly: true
    managedIdentities: {
      systemAssigned: true
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.outputs.primaryBlobEndpoint}${deploymentStorageContainerName}'
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        instanceMemoryMB: 2048
        maximumInstanceCount: 100
        alwaysReady: []
      }
      runtime: { name: 'python', version: '3.14' }
    }
    siteConfig: {
      minTlsVersion: '1.2'
      functionsRuntimeScaleMonitoringEnabled: false
    }
    configs: [{ name: 'appsettings', properties: allAppSettings }]
  }
}

module functionAppRbac './function-access.bicep' = {
  scope: rg
  name: '${functionAppName}-rbac'
  params: {
    storageAccountName: storageAccount.outputs.name
    appInsightsName: monitoring.outputs.name
    functionAppPrincipalId: functionApp.outputs.systemAssignedMIPrincipalId!
  }
}

module functionAccessPolicy './connection-access.bicep' = {
  scope: rg
  name: '${connectorNamespaceName}-func-policy'
  params: {
    connectorNamespaceName: connectorNamespace.outputs.name
    connectionName: connectorNamespace.outputs.connectionName
    functionAppPrincipalId: functionApp.outputs.systemAssignedMIPrincipalId!
  }
}

output resourceGroupResourceId string = rg.id
output resourceGroupName string = rg.name
output functionAppName string = functionApp.outputs.name
output functionAppDefaultHostname string = functionApp.outputs.defaultHostname
output connectorNamespaceName string = connectorNamespace.outputs.name
output connectorNamespaceConnectionName string = connectorNamespace.outputs.connectionName
output dataverseFunctionName string = 'OnDataverseRowChanged'
output dataverseEnvironmentUrl string = dataverseEnvironmentUrl
output dataverseTableName string = dataverseTableName
output dataverseEntitySetName string = dataverseEntitySetName
output connectorPollingEndpoint string = pollTriggers.outputs.pollingEndpoint
output triggerConfigSettings object = pollTriggers.outputs.triggerConfigSettings
