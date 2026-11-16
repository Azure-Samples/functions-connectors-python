# Azure Blob Storage webhook trigger (Python)

`OnAzureBlobUpdatedFile` receives [`OnUpdatedFiles_V2`](https://learn.microsoft.com/connectors/azureblob/#when-a-blob-is-added-or-modified-(properties-only)-(v2)) events through the Functions connector callback. It parses raw JSON and logs blob metadata and batch counts. The callback uses the `connector_extension` system key, not an ordinary function key.

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Permission to deploy resources and assign roles.
- PowerShell 7.3+ or Bash, jq 1.6+, and GNU coreutils for the deployment hook.
- A supported Python version; the template deploys Python 3.14. For local runs, install [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0b1` for Python 3.13+ or `azure-functions>=1.27.0b1` for older supported versions, and `azurefunctions-extensions-connectors>=1.0.0b4`. The requirements file selects the SDK family.

For Python 3.12 and older, set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it. Install the version-specific packages from `requirements.txt`.

## Deploy to Azure

```bash
az login
azd auth login
azd env new azureblob-webhook
azd env set BLOB_CONTAINER_NAME connector-input
azd up
```

Deployment creates a Function App, host storage, monitoring, a separate monitored storage account and container, a Connector Namespace, and a webhook trigger. The Blob connection uses the namespace's system-assigned managed identity with **Storage Blob Data Reader** on the monitored container; no OAuth consent is required.

## Optional configuration

| Setting or action | Purpose |
| --- | --- |
| `BLOB_CONTAINER_NAME` | Monitored container; defaults to `connector-input`. |
| `APPLICATIONINSIGHTS_LOCATION` | Override the monitoring region if it is unavailable in the app region. |
| `azd hooks run postdeploy` | Verify the connection and register the deployed callback; preserve existing local settings. |
| `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` or `bash ./infra/scripts/postdeploy.sh --force-local-settings` | Replace existing local settings. |

The hook waits up to five minutes for the connection to become **Ready** or **Connected**. Storage RBAC may take longer to propagate. If source polling reports authorization errors, verify the namespace identity's source role, allow propagation, and rerun the hook.

Reprovisioning an existing environment creates a separate `-mi` connection and registers the trigger against it; rerunning the hook alone does not migrate an OAuth connection. The old connection is retained.

## Local development

- Start Azurite separately.
- Use the generated local settings or copy `local.settings.example.json` to `local.settings.json` if it is absent:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

- To receive local events, expose the host through a secure public HTTPS tunnel and configure a separate callback for the local function using its local `connector_extension` system key.
- Core Tools bypasses key checks by default; enable authentication before exposing the host.
- The deployment hook registers the Azure callback, not localhost.

## Verify and clean up

Check that the `-mi` connection is Ready or Connected and the trigger is Enabled in [Connector Namespaces](https://connectors.azure.com/). Upload and overwrite a test blob in the account and container shown in azd outputs, using Microsoft Entra authentication. Allow time for detection and check function logs. Blob names and paths are logged; use test data and restrict log access.

Run `azd down --purge` from this folder to remove this environment's resources. Never commit callback keys, credentials, or local settings.
