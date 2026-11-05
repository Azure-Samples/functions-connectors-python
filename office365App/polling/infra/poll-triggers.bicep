param namespaceName string
param connectionName string
param mailFolderPath string = 'Inbox'
param calendarId string = 'Calendar'
param sharedMailboxAddress string = ''
param sharedMailboxFolderId string = 'Inbox'
param enableTriggers bool = true

var triggers = [
  {
    functionName: 'OnNewEmail'
    operationName: 'OnNewEmailV3'
    parameters: [
      { name: 'folderPath', value: mailFolderPath }
    ]
  }
  {
    functionName: 'OnFlaggedEmail'
    operationName: 'OnFlaggedEmailV4'
    parameters: [
      { name: 'folderPath', value: mailFolderPath }
    ]
  }
  {
    functionName: 'OnNewMentionMeEmail'
    operationName: 'OnNewMentionMeEmailV3'
    parameters: [
      { name: 'folderPath', value: mailFolderPath }
    ]
  }
  {
    functionName: 'OnNewCalendarEvent'
    operationName: 'CalendarGetOnNewItemsV3'
    parameters: [
      { name: 'table', value: calendarId }
    ]
  }
  {
    functionName: 'OnUpcomingEvent'
    operationName: 'OnUpcomingEventsV3'
    parameters: [
      { name: 'table', value: calendarId }
    ]
  }
  {
    functionName: 'OnCalendarUpdatedItems'
    operationName: 'CalendarGetOnUpdatedItemsV3'
    parameters: [
      { name: 'table', value: calendarId }
    ]
  }
]

var sharedMailboxTrigger = {
  functionName: 'OnSharedMailboxNewEmail'
  operationName: 'SharedMailboxOnNewEmailV2'
  parameters: [
    { name: 'mailboxAddress', value: sharedMailboxAddress }
    { name: 'folderId', value: sharedMailboxFolderId }
  ]
}
var activeTriggers = concat(triggers, empty(sharedMailboxAddress) ? [] : [sharedMailboxTrigger])

resource connectorNamespace 'Microsoft.Web/connectorGateways@2026-05-01-preview' existing = {
  name: namespaceName
}

resource triggerConfigs 'Microsoft.Web/connectorGateways/triggerConfigs@2026-05-01-preview' = [for trigger in activeTriggers: {
  parent: connectorNamespace
  name: 'office365-${toLower(trigger.functionName)}'
  properties: {
    connectionDetails: {
      connectionName: connectionName
      connectorName: 'office365'
    }
    deliveryMode: 'Poll'
    operationName: trigger.operationName
    parameters: trigger.parameters
    state: enableTriggers ? 'Enabled' : 'Disabled'
    type: 'NotSpecified'
    description: 'Office 365 ${trigger.functionName} with Poll delivery.'
  }
}]

// Use the service's receive URI, removing the trigger path and optional /api suffix.
var receiveUri = split(string(triggerConfigs[0].properties.pollingEndpoints.receiveUri), '?')[0]
var endpointBase = substring(receiveUri, 0, indexOf(toLower(receiveUri), '/triggerconfigs/'))

output pollingEndpoint string = endsWith(toLower(endpointBase), '/api')
  ? substring(endpointBase, 0, max(0, length(endpointBase) - 4))
  : endpointBase

output triggerConfigSettings object = toObject(
  concat(triggers, [sharedMailboxTrigger]),
  trigger => '${trigger.functionName}TriggerConfigName',
  trigger => 'office365-${toLower(trigger.functionName)}'
)
