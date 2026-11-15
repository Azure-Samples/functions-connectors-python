# Microsoft Dataverse connector events (Python)

Choose a standalone [polling app](./polling/README.md) or [webhook app](./webhook/README.md). Both cover these events:

| Function | Operation | Default |
| --- | --- | --- |
| `OnDataverseRowChanged` | [`SubscribeWebhookTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-a-row-is-added,-modified-or-deleted) | Enabled: row added, modified, or deleted |
| `OnDataverseActionPerformed` | [`BusinessEventsTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-an-action-is-performed) | Disabled: requires actual action-event selectors |
| `OnDataverseRowAdded` | `SubscribeOnNewItems` | Disabled: opt in to separate rows |
| `OnDataverseRowModified` | `SubscribeOnUpdatedItems` | Disabled: opt in to separate rows |
| `OnDataverseRowDeleted` | `SubscribeOnDeletedItems` | Disabled: opt in to separate rows |

All five handlers receive raw `str` payloads and log only their trigger names.

The combined trigger stays enabled by default; separate row operations are opt-in and overlap its events. Use the organization's HTTPS URL, a **logical table name** such as `account` for combined events, and the distinct **Table Name selector** from `GetTables` for separate row operations. Separate subscriptions also require the exact `GetScopeFilters` selector in `DATAVERSE_ROW_SCOPE`.

Each app includes independent infrastructure, dependencies, hooks, and safe local settings examples. Run `azd up` from the chosen folder with a separate environment name for each mode. Poll delivery does not require a public callback; webhook delivery uses the connector extension system key.

Python 3.13+ requires `azure-functions>=2.4.0b1`; older supported Python versions require `azure-functions>=1.27.0b1` and `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`. Requirements use version markers. Templates use Python 3.14. Both apps require `azurefunctions-extensions-connectors>=1.0.0b4`.

See the [Dataverse connector reference](https://learn.microsoft.com/connectors/commondataservice/).