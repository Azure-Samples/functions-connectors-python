param name string
param location string
param connectionName string
param userPrincipalId string
param tags object

resource namespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' = {
  name: name
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
}
resource connection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  parent: namespace
  name: connectionName
  properties: {
    connectorName: 'visualstudioteamservices'
    parameterValueSet: { name: 'EntraOAuth', values: {} }
  }
}
resource namespaceAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: connection
  name: 'namespace-msi'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: namespace.identity.principalId, tenantId: tenant().tenantId }
    }
  }
}
resource developerAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: connection
  name: 'dev-user'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: userPrincipalId, tenantId: tenant().tenantId }
    }
  }
}
output name string = namespace.name
output resourceId string = namespace.id
output connectionName string = connection.name
output connectionRuntimeUrl string = connection.properties.connectionRuntimeUrl