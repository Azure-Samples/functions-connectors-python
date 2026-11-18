# OneDrive for Business connector triggers (Python)

Choose the [polling app](./polling/README.md) (the Functions host pulls events; no public endpoint) or the [webhook app](./webhook/README.md) (the Connector Namespace calls the deployed function). Both cover these events:

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnOneDriveNewFileContent` | [`OnNewFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created) | `str` (file content) |
| `OnOneDriveUpdatedFileContent` | [`OnUpdatedFileV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified) | `str` (file content) |
| `OnOneDriveNewFile` | [`OnNewFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-created-(properties-only)) | `List[onedrive.BlobMetadata]` |
| `OnOneDriveUpdatedFile` | [`OnUpdatedFilesV2`](https://learn.microsoft.com/connectors/onedriveforbusiness/#when-a-file-is-modified-(properties-only)) | `List[onedrive.BlobMetadata]` |

See the [OneDrive for Business connector reference](https://learn.microsoft.com/connectors/onedriveforbusiness/).
