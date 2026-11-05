# SharePoint Online triggers (Python)

Choose the self-contained [polling app](polling/README.md) or
[webhook app](webhook/README.md). Both register these ten events. Five standard
events run by default; the other five require explicit selection and prerequisites.
Use separate azd environment names when deploying both apps.

| Function | Connector operation | Python binding | Selection |
| --- | --- | --- | --- |
| `OnSharepointNewFile` | `GetOnNewFileItems` | `list[sharepoint.Item]` | Standard |
| `OnSharepointUpdatedFile` | `GetOnUpdatedFileItems` | `list[sharepoint.Item]` | Standard |
| `OnSharepointNewItem` | `GetOnNewItems` | `list[sharepoint.Item]` | Standard |
| `OnSharepointUpdatedItem` | `GetOnUpdatedItems` | `list[sharepoint.Item]` | Standard |
| `OnSharepointChangedItem` | `GetOnChangedItems` | `list[sharepoint.Item]` | Standard |
| `OnSharepointDeletedItem` | `GetOnDeletedItems` | `list[sharepoint.DeletedItem]` | Deletion |
| `OnSharepointDeletedFile` | `GetOnDeletedFileItems` | `list[sharepoint.DeletedItem]` | Deletion |
| `OnSharepointFormSubmitted` | `GetOnNewItemsFromForm` | `list[sharepoint.Item]` | Form preview |
| `OnSharepointFileClassified` | `GetOnUpdatedFileClassifiedTimes` | `list[sharepoint.Item]` | Syntex |
| `OnSharepointRecurringDigest` | `GetOnRecurrenceDigest` | `list[sharepoint.Item]` | Digest preview |

The SDK trigger metadata declares `ItemsList` for eight operations and
`DeletedItemList` for the deletion operations. The extension exposes `Item` and
`DeletedItem`, not the .NET trigger-envelope wrapper names. These ten operations
need no raw-string fallback. `Item.dynamic_properties` retains arbitrary list
columns. `DeletedItem` exposes `id`, `name`, `file_name_with_extension`,
`deleted_by_user_name`, `time_deleted`, and `is_folder`. Handlers log batch counts,
not file names, paths, or user data.

## Source options

| azd environment setting | Default | Effect |
| --- | --- | --- |
| `SHAREPOINT_SITE_URL` | Required | Connector `dataset` for every event |
| `SHAREPOINT_LIBRARY_NAME` | `Documents` | Library name or GUID; default `table` |
| `SHAREPOINT_LIST_NAME` | Empty | `table` for list and form events; empty uses the library |
| `SHAREPOINT_FOLDER_PATH` | Empty | Adds `folderPath` only to library events |
| `SHAREPOINT_ENABLE_DELETION_TRIGGERS` | `false` | Enables both deletion sources; the connection user **must be a site collection administrator** |
| `SHAREPOINT_FORM_ID` | Empty | Enables form submissions; passes the existing identifier as `form` |
| `SHAREPOINT_ENABLE_SYNTEX_TRIGGER` | `false` | Enables classification; first apply a licensed Microsoft Syntex model to the library |
| `SHAREPOINT_DIGEST_SCHEDULE` | Empty | Enables digest with `update=true`, `add=true`, and `runSchedule`; accepts `*` or `0`–`6` |

Run `azd up` after changing source options. Both templates set
`AzureWebJobs.<FunctionName>.Disabled` for every event. The hooks also disable
previously selected source configs when you remove an opt-in. This stops source
collection rather than just stopping the listener. Updates preserve other writable
properties and do not delete/recreate configs or reset connection consent.

## Dependencies and identity

Deployment uses Python 3.14 on Linux Flex Consumption, system-assigned identity,
and identity-based storage. A separate access module grants the app storage and
monitoring roles after identity creation. Poll delivery also grants the app access
to the connection. Namespace and developer access policies stay separate.
No always-ready instances are configured.

Both apps require `azurefunctions-extensions-connectors>=1.0.0b4`, plus
`azure-functions>=2.4.0b1` on Python 3.13+, or `azure-functions>=1.27.0b1` on older
supported Python versions. Requirements markers select the SDK family. The
templates and local examples include `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`.

Both shell hooks use the same standard-library Python helper. Set `PYTHON` to an
explicit interpreter when needed. Local settings use Azurite and developer
authentication, never cloud client IDs or callback secrets. Existing local
settings remain byte-for-byte unchanged unless you request
`-ForceLocalSettings` (PowerShell) or `--force-local-settings` (Bash). Review an
existing file after changing environments or source options; preservation also
preserves old listener flags. New files are private and installed atomically.

See the [SharePoint connector reference](https://learn.microsoft.com/connectors/sharepointonline/).
Use test data, keep local settings and keys out of Git, and run `azd down --purge`
from the selected delivery folder when finished.
