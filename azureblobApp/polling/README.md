# Azure Blob connector polling sample (Python)

This app runs `OnAzureBlobUpdatedFile` for the connector operation `OnUpdatedFiles_V2`.
It matches the [webhook app](../webhook), except for the two polling decorator
arguments. The Python SDK provides Azure Blob models, but the connector binding
extension has no Blob adapter. The handler therefore receives raw JSON strings.

The host receives and acknowledges events through the Connector Namespace polling
endpoint. It needs no public callback, connector extension key, or local tunnel.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
  and [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75.0+.
- The [connector-namespace CLI extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- A supported Python version; deployment uses Python 3.14.
- `azure-functions>=2.4.0b1` for Python 3.13+, or `azure-functions>=1.27.0b1`
  for older supported versions. The requirements file selects the SDK family.
- `azurefunctions-extensions-connectors>=1.0.0b4`.
- PowerShell 7.3+ for the default hook, or Bash with jq 1.6+ and GNU coreutils.
- Permission to create resources and role assignments in the subscription.

Python 3.12 and older require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, included in
the deployed app settings, local example, and generated local settings.

## Deploy

From the repository root:

```bash
cd azureblobApp/polling
az login
azd auth login
azd env new azureblob-polling
azd env set BLOB_CONTAINER_NAME connector-input
azd up
```

Use a different environment name from webhook. The container defaults to
`connector-input`. Deployment creates a Python 3.14 Linux Flex Consumption app,
system-assigned managed identity, host storage, monitoring, a separate monitored storage account
and container, a Connector Namespace, an OAuth Blob connection, and an enabled
Poll trigger config named `azureblob-onazureblobupdatedfile`.

Set `APPLICATIONINSIGHTS_LOCATION` to a supported region before provisioning if
the app region does not offer Application Insights. An empty value uses the app region.

The monitored storage account disables shared-key access. The deploying developer
gets Storage Blob Data Contributor access to upload blobs. Authorize the connection
with this same user, or grant the consenting user the required source-storage data
access separately. OAuth source access is distinct from the host's managed identity:
function and developer connection access policies allow polling and
event receipt; they do not replace the connection user's source-storage permissions.
Allow time for role assignments to take effect.

The template does not reserve always-ready instances (`alwaysReady: []`).

The trigger uses the monitored storage account as `dataset` and base64 of the
URL-encoded container path (`%2f<container>`) as `folderId`. The host settings include
`ConnectorNamespace__pollingEndpoint`, `ConnectorNamespace__credential=managedidentity`,
and
`OnAzureBlobUpdatedFileTriggerConfigName`. The endpoint comes from the service's
receive URI, not a hardcoded region URL.

The hook opens OAuth consent if the connection is not Connected. It creates local
settings only when absent. Existing regular files remain byte-for-byte unchanged;
directories and links fail. Re-run with `azd hooks run postdeploy`. To replace
settings explicitly, run `pwsh -File infra/scripts/postdeploy.ps1 -ForceLocalSettings`
or `bash infra/scripts/postdeploy.sh --force-local-settings`. Run one writer at a time.
Settings use private staging and atomic publication. Host-storage, monitoring,
and Poll connection grants follow Function creation. System-assigned identity
needs no client-ID settings. Cloud Flex settings omit `FUNCTIONS_WORKER_RUNTIME`.

## Run locally

Install [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
After provisioning and authorizing the connection:

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt
az login
azd hooks run postdeploy
func start
```

Start Azurite separately before `func start`. The hook generates the endpoint and
trigger name in ignored local settings. Alternatively, copy `local.settings.example.json`
to `local.settings.json` and replace the endpoint placeholder with the
`connectorPollingEndpoint` azd output. Do not copy deployed managed-identity settings
locally: developer credentials from `az login` provide local access.

Stop the deployed app while listening locally, or use a separate environment.
Hosts using the same trigger configuration compete for events. The hook preserves
existing settings, so update them explicitly after changing environments.

## Verify and clean up

Check that the connection is Connected and the Poll trigger Enabled in
[Connector Namespaces](https://connectors.azure.com/). Upload a test blob to the
container shown in the `monitoredStorageAccountName` and `monitoredContainerName`
azd outputs, then overwrite it. Use Microsoft Entra authentication for uploads,
not an account key. Allow time for source polling, then check Function App logs
for the function name, blob metadata, and batch count. This sample logs metadata;
it does not copy blob contents or write Blob outputs.

> [!CAUTION]
> Blob names and paths can contain private information. Use test data, restrict
> log access, and never commit credentials or local settings. Run `azd down --purge`
> from this folder to remove only this sample's resources. Hooks never delete subscriptions.