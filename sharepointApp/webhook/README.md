# SharePoint Online webhook triggers (Python)

Connector Namespace sends SharePoint events to the Functions connector callback, authenticated with the `connector_extension` system key. Five standard events run by default; other events require explicit selection.

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

Handlers log counts, not customer data.

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- A SharePoint Online site and an account permitted to authorize access to the selected library/list and opt-in sources.
- A supported Python version; the template deploys Python 3.14. Hooks also require Python; set `PYTHON` to an interpreter path if needed. Use PowerShell on Windows or Bash on POSIX.
- For local runs, [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0` for Python 3.13+ and `azurefunctions-extensions-connectors>=1.0.0`.

For Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before installing `requirements.txt`, which does not install the older SDK, and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it.

## Deploy to Azure

```bash
az login
azd auth login
azd env new sharepoint-webhook
azd env set SHAREPOINT_SITE_URL 'https://contoso.sharepoint.com/sites/test'
azd up
```

Replace the example URL with your site and authorize the connection when prompted. The hook registers selected callbacks using the deployed app's actual hostname and connector extension system key.

## Optional configuration

| Setting | Purpose |
| --- | --- |
| `SHAREPOINT_LIBRARY_NAME` | Library name or GUID; defaults to `Documents`. |
| `SHAREPOINT_LIST_NAME` | List/form table; defaults to the library when empty. |
| `SHAREPOINT_FOLDER_PATH` | Optional folder filter for library events. |
| `SHAREPOINT_ENABLE_DELETION_TRIGGERS` | Enable deletion events; requires a site collection administrator. |
| `SHAREPOINT_FORM_ID` | Enable submissions from an existing form. |
| `SHAREPOINT_ENABLE_SYNTEX_TRIGGER` | Enable classification events; requires a licensed Syntex model applied to the library. |
| `SHAREPOINT_DIGEST_SCHEDULE` | Enable digest with `*` or `0`–`6`; includes `update=true` and `add=true`. |

Rerun `azd up` after changing source selection. The hook preserves existing consent, updates selected sources, and disables unselected sources rather than deleting them. Use `-ConsentLinkOnly` or `--consent-link-only` to obtain a consent link without writing settings or triggers, then rerun the hook after consent. Do not combine this option with `-LocalSettingsOnly` or `--local-settings-only`.

## Local development

- Start Azurite separately.
- The hook generates local settings if absent; use `-ForceLocalSettings` or `--force-local-settings` to replace existing settings.
- To generate settings without resource writes or consent, use `-LocalSettingsOnly` or `--local-settings-only`.

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

- To receive local events, expose the host through a secure public HTTPS tunnel and obtain the local `connector_extension` system key.
- Core Tools bypasses key checks by default; enable authentication before exposing the host.

- Register the tunnel origin and local key with `pwsh ./infra/scripts/postdeploy.ps1 -CallbackBaseUrl <https-origin> -ConnectorExtensionKey <local-key>` or `bash ./infra/scripts/postdeploy.sh --callback-base-url <https-origin> --connector-extension-key <local-key>`.
- This replaces deployed callbacks; run `azd hooks run postdeploy` without overrides to restore them.
- Keep keys out of shell history, transcripts, and logs.

## Verify and clean up

Check Connected consent and enabled configs in [Connector Namespaces](https://connectors.azure.com/). Create and modify files and list items, then check the corresponding function-name and count logs. Verify optional events only after meeting their prerequisites.

Run `azd down --purge` from this folder when finished. Never commit callback keys, credentials, or local settings.
