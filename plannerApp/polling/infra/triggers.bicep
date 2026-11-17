targetScope = 'subscription'

// The layer hook creates and verifies owned Poll configs after OAuth consent.
@minLength(1)
param pollingEndpoint string
@minLength(1)
param listenerSettingsEncoded string

output connectorPollingEndpoint string = pollingEndpoint
output triggerConfigSettingsEncoded string = listenerSettingsEncoded