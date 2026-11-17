targetScope = 'subscription'

@minLength(1)
param pollingEndpoint string
@minLength(1)
param settingsEncoded string

// Registration runs after consent in this layer's preprovision hook.
output connectorPollingEndpoint string = pollingEndpoint
output triggerConfigSettingsEncoded string = settingsEncoded