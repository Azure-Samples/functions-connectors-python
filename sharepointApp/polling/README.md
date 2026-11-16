# SharePoint Online polling triggers (Python)

The Functions host receives SharePoint events from the Connector Namespace polling endpoint. Five standard events run by default; other events require explicit selection. No public callback is required.

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

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- A SharePoint Online site and an account permitted to authorize access to the selected library/list and opt-in sources.
- A supported Python version; the template deploys Python 3.14. Hooks also require Python; set `PYTHON` to an interpreter path if needed. Use PowerShell on Windows or Bash on POSIX.
- For local runs, [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0b1` for Python 3.13+ or `azure-functions>=1.27.0b1` for older supported versions, and `azurefunctions-extensions-connectors>=1.0.0b4`. The requirements file selects the SDK family.

For Python 3.12 and older, set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it. Install the version-specific packages from `requirements.txt`.

## Deploy to Azure

```bash
az login
azd auth login
azd env new sharepoint-polling
azd up
```

Authorize the connection, then select a site, library, and list from the connector's choices. The hook saves the selections in the azd environment. It creates enabled Poll configs after consent, provisions the Function App using their polling endpoint, and deploys the code. Reruns preserve unrelated Function App settings while refreshing the sample-managed settings.

## Optional configuration

| Setting | Purpose |
| --- | --- |
| `SHAREPOINT_SITE_URL` | Skip the site picker with the HTTPS site URL returned by the connector. |
| `SHAREPOINT_LIBRARY_NAME` | Skip the library picker with a connector-returned library ID. |
| `SHAREPOINT_LIST_NAME` | Skip the list picker with a connector-returned list ID; an explicitly empty value uses the selected library. |
| `SHAREPOINT_FOLDER_PATH` | Optional folder filter for library events. |
| `SHAREPOINT_ENABLE_DELETION_TRIGGERS` | Enable deletion events; requires a site collection administrator. |
| `SHAREPOINT_FORM_ID` | Enable submissions from an existing form. |
| `SHAREPOINT_ENABLE_SYNTEX_TRIGGER` | Enable classification events; requires a licensed Syntex model applied to the library. |
| `SHAREPOINT_DIGEST_SCHEDULE` | Enable digest with `*` or `0`–`6`; includes `update=true` and `add=true`. |

Rerun `azd up` after changing source selection. The hook preserves existing consent and disables unselected sample-owned sources rather than deleting them. To inspect consent without writing settings or triggers, run `python ./infra/scripts/setup.py --mode polling --project . --consent-link-only` after provisioning the base layer.

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

The hook creates local settings with the endpoint, trigger names, and listener flags if absent, without resource writes or consent. To replace them, run `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` or `bash ./infra/scripts/postdeploy.sh --force-local-settings`. Use developer credentials locally. Stop the deployed app or use separate configs to avoid competing listeners.

## Verify and clean up

Check Connected consent and enabled Poll configs in [Connector Namespaces](https://connectors.azure.com/). Create and modify files and list items, then check the corresponding function-name and count logs. Verify optional events only after meeting their prerequisites.

Run `azd down --purge` from this folder when finished. Never commit credentials or local settings.
