param connectorNamespaceName string
param connectionName string
param tenantId string = tenant().tenantId
@minLength(1)
param functionAppPrincipalId string

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = {
  name: connectorNamespaceName
}
resource connection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' existing = {
  parent: connectorNamespace
  name: connectionName
}
resource functionAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: connection
  name: functionAppPrincipalId
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: functionAppPrincipalId, tenantId: tenantId }
    }
  }
}