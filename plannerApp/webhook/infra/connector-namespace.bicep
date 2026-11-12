param name string
param location string
param tags object = {}
param connectionName string
@minLength(1)
param userPrincipalId string

resource namespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' = {
  name: name
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
}
resource connection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  parent: namespace
  name: connectionName
  properties: { connectorName: 'planner' }
}
resource namespaceAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: connection
  name: 'namespace-identity'
  properties: {
    principal: { type: 'ActiveDirectory', identity: { objectId: namespace.identity.principalId, tenantId: tenant().tenantId } }
  }
}
resource developerAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: connection
  name: 'deployer'
  properties: {
    principal: { type: 'ActiveDirectory', identity: { objectId: userPrincipalId, tenantId: tenant().tenantId } }
  }
}
output name string = namespace.name
output connectionName string = connection.name