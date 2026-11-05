# OneDrive for Business polling triggers (Python)

This standalone app receives new-file and updated-file metadata and content from the Connector
Namespace polling endpoint. Metadata handlers use `list[onedrive.BlobMetadata]` and match
the [webhook app](../webhook), except for the two polling decorator arguments.
No public callback, connector extension key, or local tunnel is needed.

| Function | Operation | Trigger config |
| --- | --- | --- |
| `OnOneDriveNewFileContent` | `OnNewFileV2` | `onedrive-ononedrivenewfilecontent` |
| `OnOneDriveUpdatedFileContent` | `OnUpdatedFileV2` | `onedrive-ononedriveupdatedfilecontent` |
| `OnOneDriveNewFile` | `OnNewFilesV2` | `onedrive-ononedrivenewfile` |
| `OnOneDriveUpdatedFile` | `OnUpdatedFilesV2` | `onedrive-ononedriveupdatedfile` |

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
  and [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75.0+.
- The [connector-namespace CLI extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- A OneDrive for Business account and permission to authorize the connection.
- A supported Python version; deployment uses Python 3.14.
- `azure-functions>=2.4.0b1` on Python 3.13+, or `azure-functions>=1.27.0b1` on
  older supported versions. The requirements file selects the version family.
- `azurefunctions-extensions-connectors>=1.0.0b4` for typed metadata bindings.
- PowerShell 7.3+ for the default hook, or Bash with jq 1.6+ and GNU coreutils.

Python 3.12 and older also require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`.
The infrastructure, local example, and generated settings include it.

## Deploy

From the repository root:

```bash
cd onedriveApp/polling
az login
azd auth login
azd env new onedrive-polling
azd env set ONEDRIVE_FOLDER_ID root
azd up
```

Use a different environment name from webhook. `ONEDRIVE_FOLDER_ID` defaults to
`root`. For a subfolder, supply its **connector folder ID**, not its name or path.
The template passes that ID unchanged to the `folderId` trigger parameter.

Deployment creates a Python 3.14 Linux Flex Consumption app, system-assigned managed
identity, host storage, monitoring, a Connector Namespace, an OAuth OneDrive
connection, and four enabled Poll trigger configs. OAuth identifies the OneDrive
account; connection policies grant the function and deploying developer access
to receive and acknowledge events.

Monitoring defaults to `eastus2`, separately from the app region. Set
`TELEMETRY_LOCATION` before provisioning to choose another supported monitoring region.

The template does not reserve always-ready instances (`alwaysReady: []`).

The host uses `ConnectorNamespace__pollingEndpoint`, derived from the service's
receive URI, plus `ConnectorNamespace__credential=managedidentity`. No client ID
is needed for the system-assigned identity. The four
`<FunctionName>TriggerConfigName` settings resolve the decorators' config references.

The hook opens OAuth consent unless the connection is already Connected. Sign in
with the account whose OneDrive you want to monitor. It generates ignored local
settings only when absent. Existing regular files remain byte-for-byte unchanged;
directories and links fail. Re-run with `azd hooks run postdeploy`. To replace
settings explicitly, run `pwsh -File infra/scripts/postdeploy.ps1 -ForceLocalSettings`
or `bash infra/scripts/postdeploy.sh --force-local-settings`. Run one writer at a time.
Settings use private staging and atomic publication. The app grants host-storage,
monitoring, and Poll connection access after the Function identity exists, without
a dependency cycle. Cloud settings omit `FUNCTIONS_WORKER_RUNTIME` on Flex.

### Find a subfolder ID

If you do not already have an authorized connection, deploy the
[webhook sample](../webhook/README.md) in a separate environment without setting
`ONEDRIVE_FOLDER_ID`. Its hook authorizes the connection, lets you browse folders,
and saves the selected connector ID. Read `ONEDRIVE_FOLDER_ID` from that environment
and set it in the polling environment **before** provisioning. Use the same
OneDrive account when authorizing both connections. Remove the bootstrap webhook
environment when it is no longer needed.

## Run locally

Install [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
After provisioning and authorizing the connection:

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt
az login
azd hooks run postdeploy
func start
```

Start Azurite separately before `func start`. The hook writes the endpoint and four
trigger names to ignored local settings. Alternatively, copy
`local.settings.example.json` to `local.settings.json` and replace the endpoint
placeholder with the `connectorPollingEndpoint` output. Local execution uses
developer credentials from `az login`, not deployed managed-identity settings.

Use a separate environment or stop the deployed app first: listeners using the
same trigger configs compete for events. Update preserved local settings explicitly
when switching environments.

## Verify and clean up

In [Connector Namespaces](https://connectors.azure.com/), check that the connection
is Connected and all four Poll trigger configs are Enabled. Create and then modify a
test file smaller than 50 MB in the selected folder. Allow time for connector detection,
then check Function App logs for all four function names. Metadata handlers log
file properties; content handlers use raw `str` bindings and log only their trigger
names, not file contents. Moving an existing file
is not the same as creating a new file. Delivery can repeat; account for this when
adding side effects.

> [!CAUTION]
> The handlers log file names and paths. Use test data and restrict log access.
> Never commit private local settings or tokens. Run `azd down --purge` from this
> folder to clean up only this sample's resources. Hooks never delete subscriptions.