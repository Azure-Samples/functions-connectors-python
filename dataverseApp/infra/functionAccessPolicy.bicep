// Grants the function app's system-assigned managed identity access to the
// Dataverse (commondataservice) connection so it can call connector actions at
// runtime (e.g. the ListDataverseRows HTTP function). Kept in a separate module
// so it is applied *after* the function app is created — the function app itself
// depends on the connection's runtime URL, so the connection cannot depend on the
// function app's identity (that would be a cycle).

param connectorNamespaceName string
param connectionName string
param tenantId string = tenant().tenantId

@description('Object (principal) ID of the function app system-assigned managed identity.')
param functionAppPrincipalId string

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = {
  name: connectorNamespaceName
}

resource dataverseConnection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' existing = {
  parent: connectorNamespace
  name: connectionName
}

resource dataverseConnectionFunctionAppAccessPolicy 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: dataverseConnection
  name: 'functionapp-msi'
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: {
        objectId: functionAppPrincipalId
        tenantId: tenantId
      }
    }
  }
}
