param name string
param location string
param tags object = {}
param connectionName string
param userPrincipalId string
param tenantId string = tenant().tenantId

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' = {
  name: name
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
}

resource dataverseConnection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  parent: connectorNamespace
  name: connectionName
  properties: { connectorName: 'commondataservice' }
}

resource namespaceAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: dataverseConnection
  name: 'namespace-msi'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: connectorNamespace.identity.principalId, tenantId: tenant().tenantId }
    }
  }
}

resource userAccessPolicy 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: dataverseConnection
  name: 'dev-user'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: userPrincipalId, tenantId: tenantId }
    }
  }
}

output resourceId string = connectorNamespace.id
output name string = connectorNamespace.name
output connectionName string = dataverseConnection.name