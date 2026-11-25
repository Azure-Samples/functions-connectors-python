<!--
---
name: "Azure Functions Connector Samples (Python): SharePoint Online polling"
description: Receive SharePoint Online connector events with polling in a Python Azure Functions app deployed using Azure Developer CLI (azd).
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure
- azure-functions
urlFragment: functions-connectors-sharepoint-polling-python
---
-->

# SharePoint Online polling triggers (Python)

The Functions host pulls SharePoint events from the Connector Namespace, so no public endpoint is required.

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnSharepointNewFile` | [`GetOnNewFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-created-(properties-only)) | `List[sharepoint.Item]` |
| `OnSharepointUpdatedFile` | [`GetOnUpdatedFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-created-or-modified-(properties-only)) | `List[sharepoint.Item]` |
| `OnSharepointNewItem` | [`GetOnNewItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-created) | `List[sharepoint.Item]` |
| `OnSharepointUpdatedItem` | [`GetOnUpdatedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-created-or-modified) | `List[sharepoint.Item]` |
| `OnSharepointChangedItem` | [`GetOnChangedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-or-a-file-is-modified) | `List[sharepoint.Item]` |
| `OnSharepointDeletedItem` | [`GetOnDeletedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-deleted) | `List[sharepoint.DeletedItem]` |
| `OnSharepointDeletedFile` | [`GetOnDeletedFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-deleted) | `List[sharepoint.DeletedItem]` |
| `OnSharepointFormSubmitted` | [`GetOnNewItemsFromForm`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-form-is-submitted-(preview)) | `List[sharepoint.Item]` |
| `OnSharepointFileClassified` | [`GetOnUpdatedFileClassifiedTimes`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-classified-by-a-microsoft-syntex-model) | `List[sharepoint.Item]` |
| `OnSharepointRecurringDigest` | [`GetOnRecurrenceDigest`](https://learn.microsoft.com/connectors/sharepointonline/#recurring-digest-of-updates-(preview)) | `List[sharepoint.Item]` |

Handlers log item counts, not customer data.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+ and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python (the deployed app uses Python 3.14). Deployment hooks also run on Python (set `PYTHON` to an interpreter path if needed), with PowerShell on Windows or Bash elsewhere.
- A SharePoint Online site and an account permitted to authorize access to the sources you select.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

Python 3.13+ uses `azure-functions>=2.4.0` and `azurefunctions-extensions-connectors>=1.0.0` from `requirements.txt`. For older versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new sharepoint-polling
azd up
```

`azd up` asks you to:

1. Sign in to authorize the SharePoint connection.
2. **Configure** or **Skip** each trigger, and choose its inputs, such as the site, library, or list. Optional inputs can be skipped. Configure at least one trigger.

Deletion triggers require the connection user to be a site collection administrator. The classification trigger requires a licensed Microsoft Syntex model applied to the library.

Skipped functions are still deployed with their listeners disabled.

Choices are reused by later `azd up` runs, which also deploy your code changes. To choose again, run `azd env set POLLING_TRIGGER_INPUTS ""`, then `azd up`. To retry after a failure, rerun `azd up`.

To skip the prompts, create `trigger-inputs.json` in this folder: an array of `{ "functionName", "operationName", "parameters": [{ "name", "value" }] }` objects using connector parameter names. It takes precedence over saved choices.

| Optional setting | Purpose |
| --- | --- |
| `SHAREPOINT_SITE_URL`, `SHAREPOINT_LIBRARY_NAME`, `SHAREPOINT_LIST_NAME`, `SHAREPOINT_FOLDER_PATH` | Source inputs to use instead of picking them. |

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
2. Create and modify files and list items in the selected sources. Exercise opt-in events only after meeting their prerequisites.
3. Check the function logs for the function names and item counts.

## Deprovision

```bash
azd down --purge
```

Never commit credentials or `local.settings.json`.
