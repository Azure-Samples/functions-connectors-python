// Copyright (c) .NET Foundation. All rights reserved.
// Licensed under the MIT License.

// ----------------------------------------------------------------------------
// Subscription-scoped entrypoint used by `azd up`.
// Creates the resource group and delegates to resources.bicep.
// ----------------------------------------------------------------------------

targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the azd environment. Used to derive resource names.')
param environmentName string

@minLength(1)
@description('Primary location for all resources.')
param location string

@description('Optional. Region for the Connector Namespace. Defaults to brazilsouth (currently the only region with the required preview features).')
param connectorNamespaceLocation string = 'brazilsouth'

@description('Optional. AAD object id of a user (typically the deployer) to grant access to the connector connection so the same code can be debugged locally with `az login` credentials.')
@metadata({
  azd: {
    type: 'principalId'
  }
})
param userPrincipalId string = deployer().objectId

@description('Whether to create the storage role assignments needed for managed-identity-based AzureWebJobsStorage / Flex Consumption package deployment. Set to false when the deployer lacks Microsoft.Authorization/roleAssignments/write.')
param assignStorageRoles bool = true

@description('When true, the function app uses managed identity for AzureWebJobsStorage and the Flex Consumption package container. When false, falls back to a storage account key connection string (works without RBAC permissions).')
param useStorageManagedIdentity bool = true

var tags = {
  'azd-env-name': environmentName
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  scope: resourceGroup
  name: 'resources'
  params: {
    location: location
    environmentName: environmentName
    tags: tags
    connectorNamespaceLocation: connectorNamespaceLocation
    userPrincipalId: userPrincipalId
    assignStorageRoles: assignStorageRoles
    useStorageManagedIdentity: useStorageManagedIdentity
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup.name
output resourceGroupName string = resourceGroup.name
output FUNCTION_APP_NAME string = resources.outputs.functionAppName
output FUNCTION_APP_HOSTNAME string = resources.outputs.functionAppHostname
output functionAppName string = resources.outputs.functionAppName
output connectorNamespaceName string = resources.outputs.connectorNamespaceName
output office365ConnectionName string = resources.outputs.office365ConnectionName
output office365ConnectionRuntimeUrl string = resources.outputs.office365ConnectionRuntimeUrl
