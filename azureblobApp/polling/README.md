<!--
---
name: "Azure Functions Connector Samples (Python): Azure Blob Storage polling"
description: Receive Azure Blob Storage connector events with polling in a Python Azure Functions app deployed using Azure Developer CLI (azd).
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure
- azure-functions
urlFragment: functions-connectors-azure-blob-polling-python
---
-->

# Azure Blob Storage polling trigger (Python)

The Functions host pulls events from the Connector Namespace, so the app needs no public endpoint.

| Function | Connector operation |
| --- | --- |
| `OnAzureBlobUpdatedFile` | [`OnUpdatedFiles_V2`](https://learn.microsoft.com/connectors/azureblob/#when-a-blob-is-added-or-modified-(properties-only)-(v2)) |

The handler logs each blob's name, path, size, and modification time, plus the batch count, not blob content. Use test data and restrict log access.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+ with the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- PowerShell 7.3+ on Windows, or Bash with jq 1.6+ on macOS and Linux.
- Permission to deploy resources and assign roles.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app uses `azure-functions>=2.4.0` (Python 3.13+) and `azurefunctions-extensions-connectors>=1.0.0`; the template deploys Python 3.14. For older Python versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new azureblob-polling
azd up
```

`azd up` creates the Function App, a separate storage account and container to monitor, and a Connector Namespace with the trigger enabled. The connection uses the namespace's managed identity, so there's no sign-in prompt. Later `azd up` runs also deploy code changes. To retry after a failure, rerun `azd up`.

### Optional settings

| Setting | Purpose |
| --- | --- |
| `BLOB_CONTAINER_NAME` | Monitored container; defaults to `connector-input`. |
| `CONNECTOR_NAMESPACE_LOCATION`, `APPLICATIONINSIGHTS_LOCATION` | Override the namespace or monitoring region. |

## Local development

1. Start Azurite.
2. Create a virtual environment, install dependencies, and start the host:

   ```bash
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   az login
   func start
   ```

`azd up` creates `local.settings.json` if it doesn't exist and leaves an existing file unchanged. To regenerate it, run `bash ./infra/scripts/postdeploy.sh --force-local-settings` (or `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings`). Local runs use your developer credentials. Stop the deployed app while running locally to avoid competing listeners.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), check that the Azure Blob connection is **Ready** or **Connected** and the trigger is enabled.
2. Upload or overwrite a test blob in the storage account and container shown in the `azd up` output.
3. Allow time for detection, then check the function logs.

If the trigger reports authorization errors, role assignments may still be propagating; wait a few minutes and rerun `azd up`.

## Deprovision

```bash
azd down --purge
```

Never commit credentials or `local.settings.json`.
