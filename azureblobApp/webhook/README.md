# Azure Blob connector webhook sample (Python)

This app runs `OnAzureBlobUpdatedFile` for the Azure Blob connector operation
`OnUpdatedFiles_V2`. Its raw-string handler and metadata parser match the
[polling app](../polling); only polling's `delivery_mode` and `trigger_config_name`
decorator arguments differ. This is not the native Storage BlobTrigger.

The Python SDK provides Blob models, but the binding extension has no Blob adapter.
Do not use the .NET trigger-payload type as a Python binding annotation.

The Connector Namespace sends events to the Function App's connector callback,
authenticated with its connector extension system key. The default delivery mode
is Webhook. The shared `connection="ConnectorNamespace"` decorator argument does
not replace system-key callback authentication.

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
the infrastructure and local settings example.

## Deploy

From the repository root:

```bash
cd azureblobApp/webhook
az login
azd auth login
azd env new azureblob-webhook
azd env set BLOB_CONTAINER_NAME connector-input
azd up
```

Use a different environment name from polling. Deployment creates a Python 3.14
Linux Flex Consumption app, system-assigned managed identity, host storage, monitoring, a separate
monitored storage account and container, a Connector Namespace, and an OAuth Blob
connection. The container defaults to `connector-input`.

Set `APPLICATIONINSIGHTS_LOCATION` to a supported region before provisioning if
the app region does not offer Application Insights. An empty value uses the app region.

The monitored storage account disables shared-key access. The deploying developer
gets Storage Blob Data Contributor access for uploads. Authorize the OAuth
connection with this same user, or grant the consenting user source-storage data
access separately. Allow time for role assignments to take effect.

The post-deploy hook authorizes the connection and creates or updates the enabled Webhook trigger.
It passes the monitored account as `dataset` and base64 of `%2f<container>` as
`folderId`. Callback authentication uses the connector extension system key, not
an ordinary function key. Temporary callback-authentication files are cleaned up.
The hook also creates credential-free local settings only when absent;
existing regular files remain byte-for-byte unchanged. Directories and links fail.
Re-run with `azd hooks run postdeploy`. To replace settings explicitly, run
`pwsh -File infra/scripts/postdeploy.ps1 -ForceLocalSettings` or
`bash infra/scripts/postdeploy.sh --force-local-settings`. Run one writer at a time.
Settings use private staging and atomic publication. Storage and monitoring grants
follow Function creation; cloud Flex settings omit `FUNCTIONS_WORKER_RUNTIME`.
Webhook setup validates the existing trigger list and never deletes subscriptions.

## Run locally

Install dependencies in a virtual environment and install Functions Core Tools
and Azurite. Copy `local.settings.example.json` to `local.settings.json`, start
Azurite separately, then run `func start`.

To receive real webhook events locally, expose the host through a secure public
tunnel and configure a separate trigger callback for the local function and key.
The post-deploy hook targets the deployed app, not localhost. Use the polling
sample if you do not want a public tunnel.

## Verify and clean up

Check the connection is Connected and the trigger Enabled in
[Connector Namespaces](https://connectors.azure.com/). Upload and overwrite a test
blob in the storage account and container shown in azd outputs. Use Microsoft Entra
authentication, not an account key. Allow time for the connector to detect changes,
then check logs for the function name, blob metadata, and batch count. The sample
does not copy blob contents or write Blob outputs.

> [!CAUTION]
> The handlers log blob names and paths. Use test data and restrict log access.
> Never commit tokens, callback keys, or private local settings. Run
> `azd down --purge` from this folder when finished.