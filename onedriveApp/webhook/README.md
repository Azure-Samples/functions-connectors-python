# OneDrive for Business webhook triggers (Python)

This standalone app covers `OnOneDriveNewFile` (`OnNewFilesV2`),
`OnOneDriveUpdatedFile` (`OnUpdatedFilesV2`), `OnOneDriveNewFileContent`
(`OnNewFileV2`), and `OnOneDriveUpdatedFileContent` (`OnUpdatedFileV2`). Metadata
handlers receive `list[onedrive.BlobMetadata]` and log file properties. Content
handlers receive raw `str` payloads and log only trigger names, never file content.
The Python extension has no corresponding content-payload models. The [polling app](../polling)
has matching types and handler bodies; it adds only `delivery_mode` and
`trigger_config_name` to each decorator. Both use `connection="ConnectorNamespace"`.

The Connector Namespace sends events to the Function App's connector callback,
authenticated with its connector extension system key. Webhook is the default
delivery mode; the shared `connection` argument does not change callback authentication.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
  and [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75.0+.
- The [connector-namespace CLI extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- A OneDrive for Business account and permission to authorize the connection.
- A supported Python version; deployment uses Python 3.14.
- `azure-functions>=2.4.0b1` on Python 3.13+, or `azure-functions>=1.27.0b1` on
  older supported versions. The requirements file selects the version family.
- `azurefunctions-extensions-connectors>=1.0.0b4` for typed bindings.
- PowerShell 7.3+ for the default hook, or Bash with jq 1.6+ and GNU coreutils.

Python 3.12 and older require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, included in
the infrastructure and local settings example.

## Deploy

From the repository root:

```bash
cd onedriveApp/webhook
az login
azd auth login
azd env new onedrive-webhook
azd env set ONEDRIVE_FOLDER_ID root
azd up
```

Use a different environment name from polling. An explicit connector folder ID
or `root` skips folder browsing. To select a folder interactively on first setup,
omit the `azd env set ONEDRIVE_FOLDER_ID` command. The hook opens OAuth consent,
waits for Connected, browses folders through that connection, and saves the selected
connector ID to the azd environment. It fails on invalid selection or failed
listing, save, or registration calls. Names and display paths are not connector IDs.

Deployment creates a Python 3.14 Linux Flex Consumption app, system-assigned managed identity,
storage, monitoring, a Connector Namespace, and an OAuth OneDrive connection. The
hook creates or updates four enabled Webhook trigger configs using the deployed app's actual hostname
and the connector extension system key—not an ordinary function key. Temporary
callback files are cleaned up. It also creates credential-free local settings only
when absent and preserves existing regular files byte-for-byte. Directories and
links fail. To replace settings explicitly, run
`pwsh -File infra/scripts/postdeploy.ps1 -ForceLocalSettings` or
`bash infra/scripts/postdeploy.sh --force-local-settings`. Run one writer at a time.
Settings use private staging and atomic publication. Storage and monitoring grants
follow Function creation; cloud Flex settings omit `FUNCTIONS_WORKER_RUNTIME`.
Webhook setup validates the existing trigger list and never deletes subscriptions.

Monitoring defaults to `eastus2`, separately from the app region. Set
`TELEMETRY_LOCATION` before provisioning to choose another supported monitoring region.

Re-run setup with `azd hooks run postdeploy`. To monitor another folder, set
`ONEDRIVE_FOLDER_ID` to its connector ID and re-run the hook. To browse again, clear
the saved value first. Complete consent using the OneDrive account you want to monitor.

## Run locally

Copy `local.settings.example.json` to `local.settings.json`, install requirements
in a virtual environment, start Azurite, then run `func start`.

Receiving real webhook events locally also requires a secure public tunnel and
separate trigger configurations targeting the local function names. Authenticate
with the local connector extension system key. The post-deploy hook targets the
deployed app, not localhost. Re-run it to restore deployed callback settings after
any manual changes, or use the polling sample to avoid public tunnels.

## Verify and clean up

In [Connector Namespaces](https://connectors.azure.com/), check the connection is
Connected and all four trigger configs Enabled. Create then modify a test file
smaller than 50 MB in the selected folder, allow time for detection, and check logs
for all four function names. Content operations receive file content but the
handlers neither log nor write it. Metadata handlers log file properties.

> [!CAUTION]
> The handlers log file names and paths. Use a test folder and restrict log access.
> Never commit tokens, callback keys, or local settings. Run `azd down --purge` from
> this folder when finished.