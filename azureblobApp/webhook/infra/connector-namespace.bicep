param name string
param location string
param tags object = {}
param connectionName string

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
    parameterValueSet: { name: 'tokenBasedAuth' }
  }
}

output resourceId string = connectorNamespace.id
output name string = connectorNamespace.name
output connectionName string = connection.name
output azureblobConnectionRuntimeUrl string = connection.properties.connectionRuntimeUrl