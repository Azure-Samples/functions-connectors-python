# SharePoint Online triggers (Python)

Choose the self-contained [polling app](polling/README.md) or [webhook app](webhook/README.md). Both register these ten events. Five standard events run by default; the other five require explicit selection and prerequisites. Use separate azd environment names when deploying both apps.

| Function | Connector operation | Python binding | Selection |
| --- | --- | --- | --- |
| `OnSharepointNewFile` | [`GetOnNewFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-created-(properties-only)) | `List[sharepoint.Item]` | Standard |
| `OnSharepointUpdatedFile` | [`GetOnUpdatedFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-created-or-modified-(properties-only)) | `List[sharepoint.Item]` | Standard |
| `OnSharepointNewItem` | [`GetOnNewItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-created) | `List[sharepoint.Item]` | Standard |
| `OnSharepointUpdatedItem` | [`GetOnUpdatedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-created-or-modified) | `List[sharepoint.Item]` | Standard |
| `OnSharepointChangedItem` | [`GetOnChangedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-or-a-file-is-modified) | `List[sharepoint.Item]` | Standard |
| `OnSharepointDeletedItem` | [`GetOnDeletedItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-an-item-is-deleted) | `List[sharepoint.DeletedItem]` | Deletion |
| `OnSharepointDeletedFile` | [`GetOnDeletedFileItems`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-deleted) | `List[sharepoint.DeletedItem]` | Deletion |
| `OnSharepointFormSubmitted` | [`GetOnNewItemsFromForm`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-form-is-submitted-(preview)) | `List[sharepoint.Item]` | Form preview |
| `OnSharepointFileClassified` | [`GetOnUpdatedFileClassifiedTimes`](https://learn.microsoft.com/connectors/sharepointonline/#when-a-file-is-classified-by-a-microsoft-syntex-model) | `List[sharepoint.Item]` | Syntex |
| `OnSharepointRecurringDigest` | [`GetOnRecurrenceDigest`](https://learn.microsoft.com/connectors/sharepointonline/#recurring-digest-of-updates-(preview)) | `List[sharepoint.Item]` | Digest preview |

Handlers log batch counts, not file names, paths, or user data.

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

Run `azd up` after changing source options. Removing an opt-in disables its selected source configuration.

## Dependencies and identity

Deployment uses Python 3.14 on Flex Consumption with a system-assigned identity.

Both apps require `azurefunctions-extensions-connectors>=1.0.0`, plus `azure-functions>=2.4.0` on Python 3.13+. On older supported Python versions, install `azure-functions>=1.27.0b1` before the sample requirements and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`. The templates use Python 3.14.

See the [SharePoint connector reference](https://learn.microsoft.com/connectors/sharepointonline/). Use test data, keep local settings and keys out of Git, and run `azd down --purge` from the selected delivery folder when finished.
