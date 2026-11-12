param name string
param location string
param tags object = {}
param connectionName string
param userPrincipalId string
@description('Pinned Node sample authentication selector. No credentials belong in Bicep.')
param authenticationParameterSetName string = 'BasicAuthentication'

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' = {
  name: name
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
}

resource connection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  parent: connectorNamespace
  name: connectionName
  location: location
  properties: union({ connectorName: 'salesforce' }, empty(authenticationParameterSetName) ? {} : {
    parameterValueSet: { name: authenticationParameterSetName, values: {} }
  })
}

var principalNames = ['namespace-msi', 'dev-user']
var principalIds = { 'namespace-msi': connectorNamespace.identity.principalId, 'dev-user': userPrincipalId }
resource accessPolicies 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = [for principalName in principalNames: {
  parent: connection
  name: principalName
  properties: {
    principal: { type: 'ActiveDirectory', identity: { objectId: principalIds[principalName], tenantId: tenant().tenantId } }
  }
}]

output name string = connectorNamespace.name
output resourceId string = connectorNamespace.id
output connectionName string = connection.name