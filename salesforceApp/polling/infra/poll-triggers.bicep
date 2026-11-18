targetScope = 'resourceGroup'

@minLength(1)
param namespaceName string

@minLength(1)
@description('Base64 JSON plan saved by the consent and ownership-checking preprovision hook.')
param triggerPlan string

var plan = json(base64ToString(triggerPlan))
var selected = plan.?selected ?? []

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = {
  name: namespaceName
}

resource triggerConfigs 'Microsoft.Web/connectorGateways/triggerConfigs@2026-05-01-preview' = [
  for trigger in selected: {
    parent: connectorNamespace
    name: trigger.name
    properties: trigger.properties
  }
]

var receiveUri = empty(selected) ? '' : split(string(triggerConfigs[0].properties.pollingEndpoints.receiveUri), '?')[0]
var receivePathIndex = indexOf(toLower(receiveUri), '/triggerconfigs/')
var endpointPrefix = receivePathIndex < 0 ? '' : substring(receiveUri, 0, receivePathIndex)

output pollingEndpoint string = endsWith(toLower(endpointPrefix), '/api')
  ? substring(endpointPrefix, 0, max(length(endpointPrefix) - 4, 0))
  : endpointPrefix
output triggerConfigSettings object = plan.?settings ?? {}
