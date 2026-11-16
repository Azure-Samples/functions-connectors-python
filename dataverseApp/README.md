# Microsoft Dataverse connector events (Python)

Choose a standalone [polling app](./polling/README.md) or [webhook app](./webhook/README.md). Both cover these events:

| Function | Operation | Event |
| --- | --- | --- |
| `OnDataverseRowChanged` | [`SubscribeWebhookTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-a-row-is-added,-modified-or-deleted) | Row added, modified, or deleted |
| `OnDataverseActionPerformed` | [`BusinessEventsTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-an-action-is-performed) | Selected action performed |
| `OnDataverseRowAdded` | `SubscribeOnNewItems` | Row added |
| `OnDataverseRowModified` | `SubscribeOnUpdatedItems` | Row modified |
| `OnDataverseRowDeleted` | `SubscribeOnDeletedItems` | Row deleted |

All five handlers receive raw `str` payloads and log only their trigger names.

Both apps configure all five triggers after consent. Separate row operations overlap the combined trigger when they monitor the same table. The combined trigger uses a **logical table name** such as `account`; separate row operations use the distinct **Table Name selector** from `GetTables` and scope from `GetScopeFilters`.

Each app includes independent infrastructure, dependencies, hooks, and safe local settings examples. Run `azd up` from the chosen folder with a separate environment name for each mode. Poll delivery does not require a public callback; webhook delivery uses the connector extension system key.

Python 3.13+ requires `azure-functions>=2.4.0b1`; older supported Python versions require `azure-functions>=1.27.0b1` and `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`. Requirements use version markers. Templates use Python 3.14. Both apps require `azurefunctions-extensions-connectors>=1.0.0b4`.

See the [Dataverse connector reference](https://learn.microsoft.com/connectors/commondataservice/).