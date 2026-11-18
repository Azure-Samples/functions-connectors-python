# OneDrive for Business polling triggers (Python)

The Functions host receives OneDrive events from the Connector Namespace polling endpoint. Metadata handlers receive typed lists; content handlers receive raw `str` payloads. No public callback is required.

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnOneDriveNewFileContent` | [`OnNewFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created) | `str` |
| `OnOneDriveUpdatedFileContent` | [`OnUpdatedFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified) | `str` |
| `OnOneDriveNewFile` | [`OnNewFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created-(properties-only)) | `List[onedrive.BlobMetadata]` |
| `OnOneDriveUpdatedFile` | [`OnUpdatedFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified-(properties-only)) | `List[onedrive.BlobMetadata]` |

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

> [!CAUTION]
> Metadata handlers log file names, paths, sizes, and modification times. Use test data and restrict access to logs.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- A OneDrive for Business account and permission to authorize the connection.
- PowerShell 7.3+ or Bash, jq 1.6+, and GNU coreutils for the hook. The preprovision hook also requires Python; set `PYTHON` to an interpreter path if needed.
- A supported Python version; the template deploys Python 3.14. For local runs, install [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0` for Python 3.13+ and `azurefunctions-extensions-connectors>=1.0.0`.

For Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before installing `requirements.txt`, which does not install the older SDK, and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it.

## Deploy to Azure

```bash
az login
azd auth login
azd env new onedrive-polling
azd up
```

Authorize the new connection with the account that owns the folder, then select the folder interactively. The deployment creates enabled Poll triggers after consent, provisions the Function App using their polling endpoint, and deploys the code. Reruns preserve unrelated Function App settings while refreshing the sample-managed settings.

To skip the picker, set `ONEDRIVE_FOLDER_ID` to a connector-returned folder ID before running `azd up`. A folder name, path, or literal `root` is invalid. The connector can accept `root` at registration but fails trigger evaluation with `Invalid fileId`.

### Find a folder ID manually

Use an existing authorized OneDrive connection. For the top-level folder, invoke `GetFileByPath`:

```powershell
az connector-namespace connection invoke `
  --subscription "<connection subscription ID>" `
  -g "<connection resource group>" --namespace "<namespace name>" `
  --connection-name "<authorized OneDrive connection>" `
  --request '{"method":"GET","path":"/datasets/default/GetFileByPath","queries":{"path":"/"}}' `
  --query "response.body.Id" -o tsv
```

For subfolders, list `/datasets/default/folders`, then `/datasets/default/folders/<URL-encoded returned folder ID>`. Use the returned `Id`.

## Optional configuration

| Setting or action | Purpose |
| --- | --- |
| `TELEMETRY_LOCATION` | Monitoring region; defaults to `eastus2`. |
| `ONEDRIVE_FOLDER_ID` | Skip interactive folder selection with a connector-returned ID. |
| `azd hooks run postdeploy` | Create local settings if absent. |
| `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` or `bash ./infra/scripts/postdeploy.sh --force-local-settings` | Replace existing local settings. |

## Local development

Start Azurite separately. After provisioning, run:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
az login
func start
```

`azd up` runs the postdeploy hook, which writes the endpoint and trigger names to local settings if absent. Alternatively, copy `local.settings.example.json` and replace the endpoint with the `connectorPollingEndpoint` output. Use developer credentials locally. Stop the deployed app or use separate trigger configs to avoid competing listeners.

## Verify and clean up

Check that the connection is Connected and all four Poll configs are Enabled in [Connector Namespaces](https://connectors.azure.com/). Create and modify a test file smaller than 50 MB in the selected folder, then check logs for all four functions. Moving an existing file is not a new-file event.

Run `azd down --purge` from this folder when finished. Never commit credentials or local settings.
