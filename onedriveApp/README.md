# OneDrive for Business connector triggers (Python)

Choose a standalone [polling app](./polling/README.md) or [webhook app](./webhook/README.md). Both cover these events:

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnOneDriveNewFileContent` | [`OnNewFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created) | `str` (file content) |
| `OnOneDriveUpdatedFileContent` | [`OnUpdatedFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified) | `str` (file content) |
| `OnOneDriveNewFile` | [`OnNewFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created-(properties-only)) | `List[onedrive.BlobMetadata]` |
| `OnOneDriveUpdatedFile` | [`OnUpdatedFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified-(properties-only)) | `List[onedrive.BlobMetadata]` |

Metadata handlers log file properties; content handlers log only the trigger name, never file content.

Each app includes its own infrastructure, dependencies, hooks, and local settings example. Run `azd up` from the chosen folder, using different environment names if you deploy both. Poll delivery needs no public callback; webhook delivery uses the connector callback authenticated with the connector extension system key.

## Python requirements

| Python | Minimum Functions SDK | Required setting |
| --- | --- | --- |
| 3.13+ | `azure-functions>=2.4.0b1` | None |
| 3.12 and older supported versions | `azure-functions>=1.27.0b1` | `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` |

Both requirement files use Python-version markers and require `azurefunctions-extensions-connectors>=1.0.0b4`. Deployment uses Python 3.14.

Use a **connector folder ID**, not a display name, path, or a guessed encoding. The literal `root` is invalid even though trigger registration can succeed; evaluation fails with `Invalid fileId`. Polling requires a connector-returned ID before provisioning. The webhook picker resolves the root's real ID through `GetFileByPath` and can browse an authorized connection for subfolder IDs.

> [!CAUTION]
> These handlers log file names, paths, sizes, and modification times. Use a test folder, restrict log access, and delete resources with `azd down --purge` when done.

See the [OneDrive for Business connector reference](https://learn.microsoft.com/connectors/onedriveforbusiness/).