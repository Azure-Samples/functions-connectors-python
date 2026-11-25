<!--
---
name: "Azure Functions Connector Samples (Python): OneDrive for Business polling"
description: Receive OneDrive for Business connector events with polling in a Python Azure Functions app deployed using Azure Developer CLI (azd).
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure
- azure-functions
urlFragment: functions-connectors-onedrive-polling-python
---
-->

# OneDrive for Business polling triggers (Python)

The Functions host pulls OneDrive events from the Connector Namespace, so no public endpoint is required.

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnOneDriveNewFileContent` | [`OnNewFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created) | `str` |
| `OnOneDriveUpdatedFileContent` | [`OnUpdatedFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified) | `str` |
| `OnOneDriveNewFile` | [`OnNewFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created-(properties-only)) | `List[onedrive.BlobMetadata]` |
| `OnOneDriveUpdatedFile` | [`OnUpdatedFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified-(properties-only)) | `List[onedrive.BlobMetadata]` |

Content handlers log only the trigger name, never file content. Metadata handlers log file names, paths, sizes, and modification times, so use test data and restrict log access.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python (the deployed app uses Python 3.14). Deployment hooks also run on Python, with PowerShell on Windows or `sh` elsewhere.
- A OneDrive for Business account with permission to authorize the connection.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

Python 3.13+ uses `azure-functions>=2.4.0` and `azurefunctions-extensions-connectors>=1.0.0` from `requirements.txt`. For older versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new onedrive-polling
azd up
```

`azd up` asks you to:

1. Sign in to authorize the OneDrive connection.
2. **Configure** or **Skip** each trigger. Configure at least one.
3. Select the folder to monitor. All configured triggers use this folder.

Skipped functions are still deployed with their listeners disabled.

Choices are reused by later `azd up` runs, which also deploy your code changes. To choose again, run `azd env set POLLING_TRIGGER_INPUTS ""`, then `azd up`. To retry after a failure, rerun `azd up`.

To skip the prompts, create `trigger-inputs.json` in this folder: an array of `{ "functionName", "operationName", "parameters": [{ "name", "value" }] }` objects using connector parameter names. It takes precedence over saved choices.

| Optional setting | Purpose |
| --- | --- |
| `ONEDRIVE_FOLDER_ID` | Connector-returned folder ID to use instead of browsing. A folder name, path, or literal `root` is invalid. |

## Local development

1. Start Azurite.
2. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   python -m pip install -r requirements.txt
   ```

3. Run `az login`, then `func start`.

`azd up` creates `local.settings.json` if it doesn't exist. To regenerate it, run `sh ./infra/scripts/configure-triggers.sh finish --force-local-settings` (or `./infra/scripts/configure-triggers.ps1 finish --force-local-settings` in PowerShell). Stop the deployed app while running locally so the two don't compete for events.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), confirm the connection is Connected and the selected trigger configurations are Enabled.
2. Create, then modify, a test file smaller than 50 MB in the selected folder. Moving an existing file in doesn't count as a new file.
3. Check the function logs for the selected functions.

## Deprovision

```bash
azd down --purge
```

Never commit credentials or `local.settings.json`.
