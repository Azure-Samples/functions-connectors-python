targetScope = 'subscription'

param resourceGroupName string
param connectorNamespaceName string
param connectorNamespaceConnectionName string
@minLength(1)
param mailFolderPath string
@minLength(1)
param calendarId string
param sharedMailboxAddress string = ''
param sharedMailboxFolderId string = 'Inbox'

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' existing = {
  name: resourceGroupName
}

module pollTriggers './poll-triggers.bicep' = {
  scope: rg
  name: 'poll-triggers'
  params: {
    namespaceName: connectorNamespaceName
    connectionName: connectorNamespaceConnectionName
    mailFolderPath: mailFolderPath
    calendarId: calendarId
    sharedMailboxAddress: sharedMailboxAddress
    sharedMailboxFolderId: sharedMailboxFolderId
  }
}

output connectorPollingEndpoint string = pollTriggers.outputs.pollingEndpoint
output triggerConfigSettings object = pollTriggers.outputs.triggerConfigSettings
output triggerConfigSettingsEncoded string = base64(string(pollTriggers.outputs.triggerConfigSettings))
output office365SharedMailboxAddress string = sharedMailboxAddress
output office365MailFolderPath string = mailFolderPath
output office365CalendarId string = calendarId
output office365SharedMailboxFolderId string = sharedMailboxFolderId
