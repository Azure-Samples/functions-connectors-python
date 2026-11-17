targetScope = 'subscription'

@minLength(1)
@description('Ready Poll settings from the consent and ownership-checking preprovision hook. The hook owns trigger REST updates.')
param pollingSettingsEncoded string

output triggerConfigSettingsEncoded string = pollingSettingsEncoded