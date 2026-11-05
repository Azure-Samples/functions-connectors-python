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

@minLength(1)
param teamsGroupId string
@minLength(1)
param teamsChannelId string

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

module pollTriggers './poll-triggers.bicep' = {
  name: 'poll-triggers'
  scope: rg
  params: {
    namespaceName: connectorNamespace.outputs.name
    connectionName: connectorNamespace.outputs.connectionName
    teamsGroupId: teamsGroupId
    teamsChannelId: teamsChannelId
  }
}

var allAppSettings = union({
  AzureWebJobsStorage__credential: 'managedidentity'
  AzureWebJobsStorage__accountName: storageAccount.outputs.name
  APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
  APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.connectionString
  PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
  ConnectorNamespace__credential: 'managedidentity'
  ConnectorNamespace__pollingEndpoint: pollTriggers.outputs.pollingEndpoint
}, pollTriggers.outputs.triggerConfigSettings)

module functionApp 'br/public:avm/res/web/site:0.22.0' = {
  name: 'function-app'
  scope: rg
  params: {
    name: functionAppName
    location: location
    tags: union(tags, { 'azd-service-name': 'function-app' })
    kind: 'functionapp,linux'
    serverFarmResourceId: functionAppPlan.outputs.resourceId
    httpsOnly: true
    managedIdentities: { systemAssigned: true }
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

// Assign permissions after app creation to avoid a storage/app dependency cycle.
module functionAppAccess './function-access.bicep' = {
  name: 'function-app-access'
  scope: rg
  params: {
    principalId: functionApp.outputs.systemAssignedMIPrincipalId!
    storageAccountName: storageAccount.outputs.name
    appInsightsName: monitoring.outputs.name
    connectorNamespaceName: connectorNamespace.outputs.name
    connectionName: connectorNamespace.outputs.connectionName
  }
}

output resourceGroupName string = rg.name
output functionAppName string = functionApp.outputs.name
output connectorNamespaceName string = connectorNamespace.outputs.name
output connectorNamespaceConnectionName string = connectorNamespace.outputs.connectionName
output connectorPollingEndpoint string = pollTriggers.outputs.pollingEndpoint
output triggerConfigSettings object = pollTriggers.outputs.triggerConfigSettings