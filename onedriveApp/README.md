# OneDrive for Business connector triggers (Python)

Choose a standalone [polling app](./polling/README.md) or
[webhook app](./webhook/README.md). Both cover the four .NET reference scenarios:

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnOneDriveNewFileContent` | `OnNewFileV2` | `str` (file content) |
| `OnOneDriveUpdatedFileContent` | `OnUpdatedFileV2` | `str` (file content) |
| `OnOneDriveNewFile` | `OnNewFilesV2` | `list[onedrive.BlobMetadata]` |
| `OnOneDriveUpdatedFile` | `OnUpdatedFilesV2` | `list[onedrive.BlobMetadata]` |

Both apps use the same type annotations and handler bodies. Polling adds only
`delivery_mode=func.DeliveryMode.POLL` and
`trigger_config_name="%<FunctionName>TriggerConfigName%"` to the decorators.
Both use `connection="ConnectorNamespace"`. Metadata handlers log file properties;
content handlers log only the trigger name, never the received file content.
Content operations use raw `str` bindings because the Python extension has no
corresponding content-payload models. The Python names keep the `OnOneDrive`
prefix; each maps to the same connector operation as its .NET counterpart.

Each app includes its own infrastructure, dependencies, hooks, and local settings
example. Run `azd up` from the chosen folder, using different environment names
if you deploy both. Poll delivery needs no public callback; webhook delivery uses
the connector callback authenticated with the connector extension system key.

## Python requirements

| Python | Minimum Functions SDK | Required setting |
| --- | --- | --- |
| 3.13+ | `azure-functions>=2.4.0b1` | None |
| 3.12 and older supported versions | `azure-functions>=1.27.0b1` | `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` |

Both requirement files use Python-version markers and require
`azurefunctions-extensions-connectors>=1.0.0b4`. Deployment uses Python 3.14 and
includes isolation settings, as do the local examples.

Use a **connector folder ID**, not a display name, path, or a guessed encoding.
Set `ONEDRIVE_FOLDER_ID=root` explicitly to monitor the root folder. The webhook
hook can browse an authorized connection and save a selected folder ID for reuse.

> [!CAUTION]
> These handlers log file names, paths, sizes, and modification times. Use a test
> folder, restrict log access, and delete resources with `azd down --purge` when done.

See the [OneDrive for Business connector reference](https://learn.microsoft.com/connectors/onedriveforbusiness/).