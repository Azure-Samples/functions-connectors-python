@minLength(1)
param functionAppPrincipalId string
param storageAccountName string
param appInsightsName string
param connectorNamespaceName string
param connectorConnectionName string

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageAccountName }
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = { name: appInsightsName }
var storageRoles = [
  'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
]
var metricsRole = '3913510d-42f4-4e42-8a64-420c390055eb'
resource storageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in storageRoles: {
  name: guid(storageAccount.id, functionAppPrincipalId, role)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}]
resource metricsAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsights.id, functionAppPrincipalId, metricsRole)
  scope: appInsights
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', metricsRole)
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}
resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = { name: connectorNamespaceName }
resource connection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' existing = {
  parent: connectorNamespace
  name: connectorConnectionName
}
resource functionAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: connection
  name: 'functionapp-msi'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: functionAppPrincipalId, tenantId: tenant().tenantId }
    }
  }
}