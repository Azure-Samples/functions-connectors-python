targetScope = 'subscription'

param resourceGroupName string
param functionAppName string
param connectorNamespaceName string
param connectorNamespaceConnectionName string
@minLength(1)
param sharepointSiteUrl string
@minLength(1)
param sharepointLibraryName string
param sharepointListName string = ''
param sharepointFolderPath string = ''
param sharepointEnableDeletionTriggers bool = false
param sharepointEnableSyntexTrigger bool = false
param sharepointFormId string = ''
@allowed(['', '*', '0', '1', '2', '3', '4', '5', '6'])
param sharepointDigestSchedule string = ''

var enabledGroups = {
  standard: true
  deletion: sharepointEnableDeletionTriggers
  syntex: sharepointEnableSyntexTrigger
  form: !empty(sharepointFormId)
  digest: !empty(sharepointDigestSchedule)
}
var triggerDefinitions = [for trigger in loadJsonContent('./triggers.json'): {
  functionName: trigger.functionName
  operationName: trigger.operationName
  description: trigger.description
  enabled: enabledGroups[trigger.group]
  parameters: concat([
    { name: 'dataset', value: sharepointSiteUrl }
    { name: 'table', value: trigger.target == 'list' && !empty(sharepointListName) ? sharepointListName : sharepointLibraryName }
  ], trigger.folder && !empty(sharepointFolderPath) ? [
    { name: 'folderPath', value: sharepointFolderPath }
  ] : [], trigger.group == 'form' ? [
    { name: 'form', value: sharepointFormId }
  ] : [], trigger.group == 'digest' ? [
    { name: 'update', value: true }
    { name: 'add', value: true }
    { name: 'runSchedule', value: sharepointDigestSchedule }
  ] : [])
}]
var triggerConfigSettings = union(
  toObject(triggerDefinitions, trigger => '${trigger.functionName}TriggerConfigName', trigger => 'sharepoint-${toLower(trigger.functionName)}'),
  toObject(triggerDefinitions, trigger => 'AzureWebJobs.${trigger.functionName}.Disabled', trigger => string(!trigger.enabled))
)

resource rg 'Microsoft.Resources/resourceGroups@2025-04-01' existing = {
  name: resourceGroupName
}
module pollTriggers './poll-triggers.bicep' = {
  scope: rg
  name: 'poll-triggers'
  params: {
    namespaceName: connectorNamespaceName
    connectionName: connectorNamespaceConnectionName
    functionAppName: functionAppName
    functionAppResourceGroup: resourceGroupName
    triggers: filter(triggerDefinitions, trigger => trigger.enabled)
  }
}

output connectorPollingEndpoint string = pollTriggers.outputs.pollingEndpoint
output triggerConfigSettings object = triggerConfigSettings
output triggerConfigSettingsEncoded string = base64(string(triggerConfigSettings))
output triggerDefinitions array = triggerDefinitions
output sharepointSiteUrl string = sharepointSiteUrl
output sharepointLibraryName string = sharepointLibraryName
