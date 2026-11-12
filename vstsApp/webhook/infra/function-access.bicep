param functionPrincipalId string
param storageName string
param insightsName string
param namespaceName string
param connectionName string

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageName }
resource insights 'Microsoft.Insights/components@2020-02-02' existing = { name: insightsName }
resource namespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = { name: namespaceName }
resource connection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' existing = {
  parent: namespace
  name: connectionName
}
var storageRoles = [
  'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
  '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
]
resource storageAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for role in storageRoles: {
  scope: storage
  name: guid(storage.id, functionPrincipalId, role)
  properties: {
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
  }
}]
resource monitoringAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: insights
  name: guid(insights.id, functionPrincipalId, '3913510d-42f4-4e42-8a64-420c390055eb')
  properties: {
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
  }
}
resource functionAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: connection
  name: 'function-msi'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: functionPrincipalId, tenantId: tenant().tenantId }
    }
  }
}