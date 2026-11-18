targetScope = 'subscription'

param resourceGroupName string
param connectorNamespaceName string
// The preprovision hook completes consent, validates inputs and ownership, then saves this plan.
// The empty default lets azd validate parameters before that hook runs.
param triggerPlan string

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' existing = { name: resourceGroupName }

module pollTriggers './poll-triggers.bicep' = {
  scope: rg
  name: 'poll-triggers'
  params: {
    namespaceName: connectorNamespaceName
    triggerPlan: triggerPlan
  }
}

output connectorPollingEndpoint string = pollTriggers.outputs.pollingEndpoint
output triggerConfigSettingsEncoded string = base64(string(pollTriggers.outputs.triggerConfigSettings))

output triggerConfigSettings object = pollTriggers.outputs.triggerConfigSettings
