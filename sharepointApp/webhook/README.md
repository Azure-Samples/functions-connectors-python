# SharePoint Online webhook triggers (Python)

The Connector Namespace sends SharePoint events to the deployed function app's connector callback. The five default events are always registered; the others are opt-in.

| Function | Connector operation | Binding | Selection |
| --- | --- | --- | --- |
| `OnSharepointNewFile` | [`GetOnNewFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-created-(properties-only)) | `List[sharepoint.Item]` | Default |
| `OnSharepointUpdatedFile` | [`GetOnUpdatedFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-created-or-modified-(properties-only)) | `List[sharepoint.Item]` | Default |
| `OnSharepointNewItem` | [`GetOnNewItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-created) | `List[sharepoint.Item]` | Default |
| `OnSharepointUpdatedItem` | [`GetOnUpdatedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-created-or-modified) | `List[sharepoint.Item]` | Default |
| `OnSharepointChangedItem` | [`GetOnChangedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-or-a-file-is-modified) | `List[sharepoint.Item]` | Default |
| `OnSharepointDeletedItem` | [`GetOnDeletedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-deleted) | `List[sharepoint.DeletedItem]` | Deletion |
| `OnSharepointDeletedFile` | [`GetOnDeletedFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-deleted) | `List[sharepoint.DeletedItem]` | Deletion |
| `OnSharepointFormSubmitted` | [`GetOnNewItemsFromForm`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-form-is-submitted-(preview)) | `List[sharepoint.Item]` | Form |
| `OnSharepointFileClassified` | [`GetOnUpdatedFileClassifiedTimes`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-classified-by-a-microsoft-syntex-model) | `List[sharepoint.Item]` | Syntex |
| `OnSharepointRecurringDigest` | [`GetOnRecurrenceDigest`](https://learn.microsoft.com/connectors/sharepointonline/#recurring-digest-of-updates-(preview)) | `List[sharepoint.Item]` | Digest |

Handlers log item counts, not customer data.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+ and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python (the deployed app uses Python 3.14). Deployment hooks also run on Python (set `PYTHON` to an interpreter path if needed), with PowerShell on Windows or Bash elsewhere.
- A SharePoint Online site and an account permitted to authorize access to the sources you select.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

Python 3.13+ uses `azure-functions>=2.4.0` and `azurefunctions-extensions-connectors>=1.0.0` from `requirements.txt`. For older versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new sharepoint-webhook
azd env set SHAREPOINT_SITE_URL 'https://contoso.sharepoint.com/sites/test'
azd up
```

Replace the example URL with your site, and sign in to authorize the connection when prompted. Later `azd up` runs deploy your code changes and apply setting changes. To retry after a failure, rerun `azd up`.

Use `azd env set` to change the source or enable opt-in events, then rerun `azd up`. Removing an opt-in disables its trigger configuration.

| Optional setting | Purpose |
| --- | --- |
| `SHAREPOINT_LIBRARY_NAME` | Library name or GUID; defaults to `Documents`. |
| `SHAREPOINT_LIST_NAME` | List for list and form events; defaults to the library. |
| `SHAREPOINT_FOLDER_PATH` | Folder filter for library events. |
| `SHAREPOINT_ENABLE_DELETION_TRIGGERS` | `true` enables deletion events. |
| `SHAREPOINT_FORM_ID` | Enables submissions from an existing form. |
| `SHAREPOINT_ENABLE_SYNTEX_TRIGGER` | `true` enables classification events. |
| `SHAREPOINT_DIGEST_SCHEDULE` | Enables the digest; `*` or `0`–`6`. |

Deletion triggers require the connection user to be a site collection administrator. The classification trigger requires a licensed Microsoft Syntex model applied to the library.

## Local development

1. Start Azurite.
2. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   python -m pip install -r requirements.txt
   ```

3. Run `func start --enableAuth`.

`azd up` creates `local.settings.json` if it doesn't exist. To regenerate it without changing Azure resources, run `bash ./infra/scripts/postdeploy.sh --local-settings-only --force-local-settings` (or `./infra/scripts/postdeploy.ps1 -LocalSettingsOnly -ForceLocalSettings` in PowerShell).

To receive events locally, expose the host through a secure HTTPS tunnel, then point the callbacks at it with `bash ./infra/scripts/postdeploy.sh --callback-base-url <https-origin> --connector-extension-key <local-key>` (or `-CallbackBaseUrl`/`-ConnectorExtensionKey` in PowerShell), using the local `connector_extension` system key. Core Tools skips key checks unless you pass `--enableAuth`. Run `azd up` again to restore the deployed callbacks, and keep keys out of shell history and logs.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), confirm the connection is Connected and the selected trigger configurations are Enabled.
2. Create and modify files and list items in the selected sources. Exercise opt-in events only after meeting their prerequisites.
3. Check the function logs for the function names and item counts.

## Deprovision

```bash
azd down --purge
```

Never commit callback keys, credentials, or `local.settings.json`.
