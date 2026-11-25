<!--
---
name: "Azure Functions Connector Samples (Python): Azure Blob Storage webhook"
description: Receive Azure Blob Storage connector events through webhook delivery in a Python Azure Functions app deployed using Azure Developer CLI (azd).
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure
- azure-functions
urlFragment: functions-connectors-azure-blob-webhook-python
---
-->

# Azure Blob Storage webhook trigger (Python)

The Connector Namespace calls the deployed function's connector callback, authenticated with the `connector_extension` system key.

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
azd env new azureblob-webhook
azd up
```

`azd up` creates the Function App, a separate storage account and container to monitor, and a Connector Namespace, then registers the trigger with the deployed function's callback. The connection uses the namespace's managed identity, so there's no sign-in prompt. Later `azd up` runs also deploy code changes. To retry after a failure, rerun `azd up`.

### Optional settings

| Setting | Purpose |
| --- | --- |
| `BLOB_CONTAINER_NAME` | Monitored container; defaults to `connector-input`. |
| `CONNECTOR_NAMESPACE_LOCATION`, `APPLICATIONINSIGHTS_LOCATION` | Override the namespace or monitoring region. |

## Local development

1. Start Azurite.
2. Create a virtual environment, install dependencies, and start the host with authentication enabled:

   ```bash
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   func start --enableAuth
   ```

`azd up` creates `local.settings.json` if it doesn't exist and leaves an existing file unchanged; you can also copy `local.settings.example.json`. To regenerate it, run `bash ./infra/scripts/postdeploy.sh --force-local-settings` (or `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings`).

The deployed callback points to Azure, not localhost. To receive events locally, expose the host through a secure HTTPS tunnel and configure a separate callback that uses the local `connector_extension` system key. Core Tools skips key checks unless started with `--enableAuth`.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), check that the Azure Blob connection is **Ready** or **Connected** and the trigger is enabled.
2. Upload or overwrite a test blob in the storage account and container shown in the `azd up` output, using Microsoft Entra authentication.
3. Allow time for detection, then check the function logs.

If the trigger reports authorization errors, role assignments may still be propagating; wait a few minutes and rerun `azd up`.

## Deprovision

```bash
azd down --purge
```

Never commit callback keys, credentials, or `local.settings.json`.
