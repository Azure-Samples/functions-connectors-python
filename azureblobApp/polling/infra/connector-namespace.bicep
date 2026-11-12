param name string
param location string
param tags object = {}
param connectionName string
param userPrincipalId string = ''

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' = {
  name: name
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
}

resource connection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  parent: connectorNamespace
  name: connectionName
  properties: {
    connectorName: 'azureblob'
    parameterValueSet: { name: 'managedIdentityAuth', values: {} }
    connectionProperties: {
      authentication: { type: 'ManagedServiceIdentity' }
    }
  }
}

resource namespaceAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: connection
  name: 'namespace-msi'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: connectorNamespace.identity.principalId, tenantId: tenant().tenantId }
    }
  }
}

resource developerAccess 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = if (!empty(userPrincipalId)) {
  parent: connection
  name: 'dev-user'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: { objectId: userPrincipalId, tenantId: tenant().tenantId }
    }
  }
}

output resourceId string = connectorNamespace.id
output name string = connectorNamespace.name
output principalId string = connectorNamespace.identity.principalId
output connectionName string = connection.name
output azureblobConnectionRuntimeUrl string = connection.properties.connectionRuntimeUrl