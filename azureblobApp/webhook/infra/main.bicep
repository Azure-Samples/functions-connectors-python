targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Environment name used to generate unique resource names. Use a different name from the polling sample.')
param environmentName string

@metadata({
  azd: {
    type: 'location'
  }
})
@description('Location for all resources except the Connector Namespace.')
param location string

@description('Region for the Connector Namespace. Override via CONNECTOR_NAMESPACE_LOCATION if needed.')
param connectorNamespaceLocation string = 'westcentralus'

@description('Application Insights region. Empty uses the app location.')
param applicationInsightsLocation string = ''

@description('Name of the blob container to monitor for trigger events.')
param monitoredContainerName string = 'connector-input'

metadata name = 'Azure Functions Azure Blob Webhook Connector Trigger (Python)'
metadata description = 'Connector Namespace webhook delivery using system key authentication on the callback URL.'

@description('Developer identity for source blob uploads, connection access, and local host storage.')
@metadata({
  azd: {
    type: 'principalId'
  }
})
param userPrincipalId string = deployer().objectId

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

var functionAppName = '${abbrs.webSitesFunctions}${resourceToken}'
var functionAppPlanName = '${abbrs.webServerFarms}${resourceToken}'
var resourceGroupName = '${abbrs.resourcesResourceGroups}${environmentName}'
var storageAccountName = '${abbrs.storageStorageAccounts}${resourceToken}'
var logAnalyticsName = '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
var appInsightsName = '${abbrs.insightsComponents}${resourceToken}'
var connectorNamespaceName = '${abbrs.connectorNamespaces}${resourceToken}'
var connectorNamespaceConnectionName = '${abbrs.connectorNamespacesConnections}${resourceToken}'
var monitoredStorageAccountName = '${abbrs.storageStorageAccounts}mon${take(resourceToken, 20)}'

var deploymentStorageContainerName = 'app-package-${take(functionAppName, 32)}-${take(toLower(uniqueString(functionAppName, environmentName)), 7)}'
var storageBlobDataOwner = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageBlobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
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
    location: location
    tags: tags
    dataRetention: 30
  }
}

module monitoring 'br/public:avm/res/insights/component:0.7.1' = {
  name: '${uniqueString(deployment().name, location)}-appinsights'
  scope: rg
  params: {
    name: appInsightsName
    location: empty(applicationInsightsLocation) ? location : applicationInsightsLocation
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
    networkAcls: {
      defaultAction: 'Allow'
    }
    minimumTlsVersion: 'TLS1_2'
    blobServices: {
      containers: [{ name: deploymentStorageContainerName }]
    }
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

// Keep source blobs separate from host and deployment storage.
module monitoredStorageAccount 'br/public:avm/res/storage/storage-account:0.32.0' = {
  scope: rg
  name: monitoredStorageAccountName
  params: {
    name: monitoredStorageAccountName
    location: location
    tags: tags
    skuName: 'Standard_LRS'
    kind: 'StorageV2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    minimumTlsVersion: 'TLS1_2'
    blobServices: {
      containers: [
        {
          name: monitoredContainerName
          roleAssignments: [
            {
              roleDefinitionIdOrName: storageBlobDataReader
              principalId: connectorNamespace.outputs.principalId
              principalType: 'ServicePrincipal'
            }
          ]
        }
      ]
    }
    roleAssignments: [
      {
        roleDefinitionIdOrName: storageBlobDataContributor
        principalId: userPrincipalId
        principalType: 'User'
      }
    ]
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

var allAppSettings = {
  AzureWebJobsStorage__credential: 'managedidentity'
  AzureWebJobsStorage__accountName: storageAccount.outputs.name
  APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'Authorization=AAD'
  APPLICATIONINSIGHTS_CONNECTION_STRING: monitoring.outputs.connectionString
  PYTHON_ISOLATE_WORKER_DEPENDENCIES: '1'
  ConnectorNamespace__credential: 'managedidentity'
  AZUREBLOB_CONNECTION_RUNTIME_URL: connectorNamespace.outputs.azureblobConnectionRuntimeUrl
}

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
      }
      runtime: {
        name: 'python'
        version: '3.14'
      }
    }
    siteConfig: {
      minTlsVersion: '1.2'
    }
    configs: [
      {
        name: 'appsettings'
        properties: allAppSettings
      }
    ]
  }
}

module functionAccess './function-access.bicep' = {
  name: 'function-access'
  scope: rg
  params: {
    storageAccountName: storageAccount.outputs.name
    appInsightsName: monitoring.outputs.name
    functionAppPrincipalId: functionApp.outputs.systemAssignedMIPrincipalId!
  }
}

@description('The resource ID of the created Resource Group.')
output resourceGroupResourceId string = rg.id

@description('The name of the created Resource Group.')
output resourceGroupName string = rg.name

@description('The name of the created Function App.')
output functionAppName string = functionApp.outputs.name

@description('The default hostname of the created Function App.')
output functionAppDefaultHostname string = functionApp.outputs.defaultHostname

@description('The name of the created Connector Namespace.')
output connectorNamespaceName string = connectorNamespace.outputs.name

@description('The principal ID of the Connector Namespace managed identity used for source blob access.')
output connectorNamespacePrincipalId string = connectorNamespace.outputs.principalId

@description('The name of the Azure Blob connection on the Connector Namespace.')
output connectorNamespaceConnectionName string = connectorNamespace.outputs.connectionName

@description('The name of the Azure Function that handles the blob trigger.')
output azureblobFunctionName string = 'OnAzureBlobUpdatedFile'

@description('The name of the storage account monitored by the blob trigger.')
output monitoredStorageAccountName string = monitoredStorageAccount.outputs.name

@description('The name of the blob container monitored by the trigger.')
output monitoredContainerName string = monitoredContainerName