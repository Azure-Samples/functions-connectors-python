# OneDrive for Business webhook triggers (Python)

The Connector Namespace sends OneDrive events to the deployed function app's connector callback.

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnOneDriveNewFileContent` | [`OnNewFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created) | `str` |
| `OnOneDriveUpdatedFileContent` | [`OnUpdatedFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified) | `str` |
| `OnOneDriveNewFile` | [`OnNewFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created-(properties-only)) | `List[onedrive.BlobMetadata]` |
| `OnOneDriveUpdatedFile` | [`OnUpdatedFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified-(properties-only)) | `List[onedrive.BlobMetadata]` |

Content handlers log only the trigger name, never file content. Metadata handlers log file names, paths, sizes, and modification times, so use test data and restrict log access.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- PowerShell 7.3+ on Windows, or Bash and [jq](https://jqlang.org/) elsewhere.
- Python (the deployed app uses Python 3.14).
- A OneDrive for Business account with permission to authorize the connection.
- For local runs: [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

Python 3.13+ uses `azure-functions>=2.4.0` and `azurefunctions-extensions-connectors>=1.0.0` from `requirements.txt`. For older versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new onedrive-webhook
azd up
```

`azd up` asks you to:

1. Sign in to authorize the OneDrive connection.
2. Select the folder to monitor.

All four triggers are then registered against the deployed app. Later `azd up` runs deploy your code changes. To retry after a failure, rerun `azd up`.

| Optional setting | Purpose |
| --- | --- |
| `ONEDRIVE_FOLDER_ID` | Connector-returned folder ID to use instead of browsing. A folder name, path, or literal `root` is invalid. Set a new ID and rerun `azd up` to change folders. |
| `TELEMETRY_LOCATION` | Monitoring region; defaults to `eastus2`. |

## Local development

1. Start Azurite.
2. Create and activate a virtual environment, then install dependencies:

   ```bash
   python -m venv .venv
   python -m pip install -r requirements.txt
   ```

3. Run `func start --enableAuth`.

`azd up` creates `local.settings.json` if it doesn't exist. To regenerate it, run `bash ./infra/scripts/postdeploy.sh --force-local-settings` (or `./infra/scripts/postdeploy.ps1 -ForceLocalSettings` in PowerShell).

Registered callbacks point to Azure, not localhost. To receive events locally, expose the host through a secure HTTPS tunnel and register separate trigger configurations that use the local `connector_extension` system key. Core Tools skips key checks unless you pass `--enableAuth`.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), confirm the connection is Connected and all four trigger configurations are Enabled.
2. Create, then modify, a test file smaller than 50 MB in the selected folder.
3. Check the function logs for all four functions.

## Deprovision

```bash
azd down --purge
```

Never commit callback keys, credentials, or `local.settings.json`.
