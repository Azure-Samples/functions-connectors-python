// Copyright (c) .NET Foundation. All rights reserved.
// Licensed under the MIT License.

// ----------------------------------------------------------------------------
// Resource-group-scoped resources: Storage, App Insights, Function App,
// Connector Namespace + Teams connection.
// Uses the Flex Consumption (FC1) hosting plan.
// ----------------------------------------------------------------------------

@minLength(1)
param environmentName string

@minLength(1)
param location string

@description('Optional override for the Connector Namespace location. Connector Namespace is currently only available in a subset of regions, so we default to a known-good region rather than the function app location.')
param connectorNamespaceLocation string = 'brazilsouth'

param tags object = {}

@description('Optional. AAD object id of a user (typically the deployer) to grant access to the connection so the same code can be debugged locally with `az login`.')
param userPrincipalId string = ''

@description('Whether to create the storage role assignments needed for managed-identity AzureWebJobsStorage and Flex Consumption package deployment. Set to false when the deployer lacks Microsoft.Authorization/roleAssignments/write.')
param assignStorageRoles bool = true

@description('When true, the function app uses managed identity for AzureWebJobsStorage and the Flex Consumption package container. When false, falls back to a storage account key connection string.')
param useStorageManagedIdentity bool = true

@description('Maximum scale-out instance count for the Flex Consumption plan.')
param maximumInstanceCount int = 100

@description('Per-instance memory size (MB) for the Flex Consumption plan.')
@allowed([
  512
  2048
  4096
])
param instanceMemoryMB int = 2048

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var storageAccountName = take('st${replace(resourceToken, '-', '')}', 24)
var planName = 'plan-${environmentName}-${resourceToken}'
var functionAppName = 'func-${environmentName}-${resourceToken}'
var appInsightsName = 'appi-${environmentName}-${resourceToken}'
var logAnalyticsName = 'log-${environmentName}-${resourceToken}'
var connectorNamespaceName = 'cn${resourceToken}'
var teamsConnectionName = 'teams-${resourceToken}'
var deploymentContainerName = 'app-package'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
  tags: tags
}

resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: deploymentContainerName
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
  tags: tags
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
  tags: tags
}

resource appPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: planName
  location: location
  kind: 'functionapp'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
  tags: tags
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appPlan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}${deploymentContainerName}'
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: maximumInstanceCount
        instanceMemoryMB: instanceMemoryMB
      }
      runtime: {
        name: 'python'
        version: '3.13'
      }
    }
    siteConfig: {
      ftpsState: 'FtpsOnly'
      minTlsVersion: '1.2'
    }
  }
  tags: union(tags, {
    'azd-service-name': 'api'
  })
  dependsOn: [
    deploymentContainer
  ]
}

module connectorNamespace './connectorNamespace.bicep' = {
  name: 'connectorNamespace-${connectorNamespaceName}'
  params: {
    name: connectorNamespaceName
    location: connectorNamespaceLocation
    tags: tags
    teamsConnectionName: teamsConnectionName
    functionAppPrincipalId: functionApp.identity.principalId
    userPrincipalId: userPrincipalId
  }
}

// App settings live in a separate sub-resource so they can reference
// outputs from the connectorNamespace module without creating a cycle
// with the function app's identity principalId.
var storageConnectionString = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storage.listKeys().keys[0].value}'

var baseAppSettings = {
  APPLICATIONINSIGHTS_CONNECTION_STRING: appInsights.properties.ConnectionString
  TeamsConnection: connectorNamespace.outputs.teamsConnectionRuntimeUrl
}

var identityStorageSettings = {
  AzureWebJobsStorage__accountName: storage.name
}

var connectionStringStorageSettings = {
  AzureWebJobsStorage: storageConnectionString
  DEPLOYMENT_STORAGE_CONNECTION_STRING: storageConnectionString
}

resource functionAppSettings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: functionApp
  name: 'appsettings'
  properties: union(baseAppSettings, useStorageManagedIdentity ? identityStorageSettings : connectionStringStorageSettings)
}

// Grant the function app's managed identity access to the storage account
// (required for Flex Consumption deployment package and AzureWebJobsStorage identity-based auth).
var storageBlobDataOwnerRoleId = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource storageBlobDataOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignStorageRoles) {
  scope: storage
  name: guid(storage.id, functionApp.id, storageBlobDataOwnerRoleId)
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataOwnerRoleId)
    principalType: 'ServicePrincipal'
  }
}

resource storageBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (assignStorageRoles) {
  scope: storage
  name: guid(storage.id, functionApp.id, storageBlobDataContributorRoleId)
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalType: 'ServicePrincipal'
  }
}

output functionAppName string = functionApp.name
output functionAppHostname string = functionApp.properties.defaultHostName
output connectorNamespaceName string = connectorNamespace.outputs.name
output teamsConnectionName string = connectorNamespace.outputs.teamsConnectionName
output teamsConnectionRuntimeUrl string = connectorNamespace.outputs.teamsConnectionRuntimeUrl
