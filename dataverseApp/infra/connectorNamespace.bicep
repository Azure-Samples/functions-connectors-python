// Connector Namespace + Common Data Service / Dataverse (commondataservice) connection
// using OAuth. Requires interactive consent during post-deploy to authenticate;
// sign in with an account that has access to the target Dataverse environment.

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

resource dataverseConnection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  parent: connectorNamespace
  name: connectionName
  properties: {
    connectorName: 'commondataservice'
  }
}

// Connector Namespace system MI -> Dataverse connection (needed to poll triggers).
resource dataverseConnectionNamespaceAccessPolicy 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: dataverseConnection
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

@description('The name of the Dataverse connection on the namespace.')
output connectionName string = dataverseConnection.name

@description('Runtime URL for the Dataverse connection.')
output dataverseConnectionRuntimeUrl string = dataverseConnection.properties.connectionRuntimeUrl
