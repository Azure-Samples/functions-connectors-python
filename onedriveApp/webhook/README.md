# OneDrive for Business webhook triggers (Python)

Connector Namespace sends OneDrive events to the Functions connector callback, authenticated with the `connector_extension` system key. Metadata handlers receive typed lists; content handlers receive raw `str` payloads.

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnOneDriveNewFileContent` | [`OnNewFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created) | `str` |
| `OnOneDriveUpdatedFileContent` | [`OnUpdatedFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified) | `str` |
| `OnOneDriveNewFile` | [`OnNewFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created-(properties-only)) | `List[onedrive.BlobMetadata]` |
| `OnOneDriveUpdatedFile` | [`OnUpdatedFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified-(properties-only)) | `List[onedrive.BlobMetadata]` |

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- A OneDrive for Business account and permission to authorize the connection.
- PowerShell 7.3+ or Bash, jq 1.6+, and GNU coreutils for the hook.
- A supported Python version; the template deploys Python 3.14. For local runs, install [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0b1` for Python 3.13+ or `azure-functions>=1.27.0b1` for older supported versions, and `azurefunctions-extensions-connectors>=1.0.0b4`. The requirements file selects the SDK family.

For Python 3.12 and older, set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it. Install the version-specific packages from `requirements.txt`.

## Deploy to Azure

```bash
az login
azd auth login
azd env new onedrive-webhook
azd up
```

Complete OAuth consent and select a folder when prompted. To skip browsing, set `ONEDRIVE_FOLDER_ID` to its **connector-returned ID** before `azd up`. Do not use a folder name, path, or literal `root`: `root` can register but fails trigger evaluation with `Invalid fileId`. The interactive root selection resolves the real ID.

The hook registers four webhook configs with the deployed app's actual hostname and connector extension system key. It preserves existing local settings.

## Optional configuration

| Setting or action | Purpose |
| --- | --- |
| `ONEDRIVE_FOLDER_ID` | Explicit connector-returned folder ID; omit to select interactively. |
| `TELEMETRY_LOCATION` | Monitoring region; defaults to `eastus2`. |
| `azd hooks run postdeploy` | Rerun setup; set a new folder ID first to change the monitored folder. |
| `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` or `bash ./infra/scripts/postdeploy.sh --force-local-settings` | Replace existing local settings. |

## Local development

- Start Azurite separately.
- Use the generated local settings or copy `local.settings.example.json` to `local.settings.json` if absent:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

- To receive local events, expose the host through a secure public HTTPS tunnel and configure separate callbacks for the local functions using the local `connector_extension` system key.
- Core Tools bypasses key checks by default; enable authentication before exposing the host.
- The hook targets Azure, not localhost; rerun it to restore deployed callbacks after manual changes.

## Verify and clean up

Check that the connection is Connected and all four configs are Enabled in [Connector Namespaces](https://connectors.azure.com/). Create and modify a test file smaller than 50 MB in the selected folder, then check logs for all four functions. Metadata handlers log file properties; use test data and restrict log access.

Run `azd down --purge` from this folder when finished. Never commit callback keys, credentials, or local settings.
