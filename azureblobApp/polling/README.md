# Azure Blob Storage polling trigger (Python)

`OnAzureBlobUpdatedFile` receives [`OnUpdatedFiles_V2`](https://learn.microsoft.com/connectors/azureblob/#when-a-blob-is-added-or-modified-(properties-only)-(v2)) events through Connector Namespace Poll delivery. It parses raw JSON and logs blob metadata and batch counts. Poll delivery does not require a public callback.

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Permission to deploy resources and assign roles.
- PowerShell 7.3+ or Bash, jq 1.6+, and GNU coreutils for the deployment hook.
- A supported Python version; the template deploys Python 3.14. For local runs, install [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0` for Python 3.13+ and `azurefunctions-extensions-connectors>=1.0.0`.

For Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before installing `requirements.txt`, which does not install the older SDK, and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it.

## Deploy to Azure

```bash
az login
azd auth login
azd env new azureblob-polling
azd env set BLOB_CONTAINER_NAME connector-input
azd up
```

Deployment creates a Function App, host storage, monitoring, a separate monitored storage account and container, a Connector Namespace, and an enabled Poll trigger. The Blob connection uses the namespace's system-assigned managed identity with **Storage Blob Data Reader** on the monitored container; no OAuth consent is required.

## Optional configuration

| Setting or action | Purpose |
| --- | --- |
| `BLOB_CONTAINER_NAME` | Monitored container; defaults to `connector-input`. |
| `APPLICATIONINSIGHTS_LOCATION` | Override the monitoring region if it is unavailable in the app region. |
| `azd hooks run postdeploy` | Verify connection authentication and readiness and create local settings if absent. |
| `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` or `bash ./infra/scripts/postdeploy.sh --force-local-settings` | Replace existing local settings rather than preserving them. |

The hook waits up to five minutes for the connection to become **Ready** or **Connected**. Storage RBAC may take longer to propagate. If source polling reports authorization errors, verify the namespace identity's source role, allow propagation, and rerun the hook.

Reprovisioning an existing environment creates a separate `-mi` connection and switches the trigger to it; rerunning the hook alone does not migrate an OAuth connection. The old connection is retained.

## Local development

Start Azurite separately. After provisioning, run:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
az login
azd hooks run postdeploy
func start
```

The hook generates `local.settings.json` with the polling endpoint and trigger name, or preserves an existing file. Alternatively, copy `local.settings.example.json` and replace the endpoint with the `connectorPollingEndpoint` azd output. Use developer credentials locally, not deployed managed-identity settings. Stop the deployed app or use separate trigger configs to avoid competing listeners.

## Verify and clean up

Check that the `-mi` connection is Ready or Connected and the Poll trigger is Enabled in [Connector Namespaces](https://connectors.azure.com/). Upload and overwrite a test blob in the account and container shown in azd outputs, using Microsoft Entra authentication. Allow time for detection and check function logs. Blob names and paths are logged; use test data and restrict log access.

Run `azd down --purge` from this folder to remove this environment's resources. Never commit credentials or local settings.
