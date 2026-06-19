param name string
param location string
param tags object = {}
param connectionName string
param tenantId string = tenant().tenantId

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
}

resource onedriveConnection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  parent: connectorNamespace
  name: connectionName
  properties: {
    connectorName: 'onedriveforbusiness'
  }
}

// Connector Namespace system MI -> OneDrive connection (needed to poll triggers).
resource onedriveConnectionNamespaceAccessPolicy 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: onedriveConnection
  name: 'connector-namespace-msi'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: {
        objectId: connectorNamespace.identity.principalId
        tenantId: tenantId
      }
    }
  }
}

@description('The resource ID of the Connector Namespace.')
output resourceId string = connectorNamespace.id

@description('The name of the Connector Namespace.')
output name string = connectorNamespace.name

@description('The name of the OneDrive connection on the namespace.')
output connectionName string = onedriveConnection.name

@description('Runtime URL for the OneDrive connection.')
output onedriveConnectionRuntimeUrl string = onedriveConnection.properties.connectionRuntimeUrl
