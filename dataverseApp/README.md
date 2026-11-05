# Microsoft Dataverse connector events (Python)

Choose a standalone [polling app](./polling/README.md) or
[webhook app](./webhook/README.md). Both match the current events in the
[.NET reference](https://github.com/Azure-Samples/functions-connectors-net/pull/13):

| Function | Operation | Default |
| --- | --- | --- |
| `OnDataverseRowChanged` | `SubscribeWebhookTrigger` | Enabled: row added, modified, or deleted |
| `OnDataverseActionPerformed` | `BusinessEventsTrigger` | Disabled: requires actual action-event selectors |
| `OnDataverseRowAdded` | `GetOnNewItems_V2` | Disabled: opt in to separate rows |
| `OnDataverseRowModified` | `GetOnUpdatedItems_V2` | Disabled: opt in to separate rows |
| `OnDataverseRowDeleted` | `GetOnDeletedItems_V2` | Disabled: opt in to separate rows |

All five handlers receive raw `str` payloads and log only their trigger names. Python
has no matching Dataverse extension models; the older `list[commondataservice.Item]`
binding is not used. Handler code matches between delivery modes; polling adds
only `delivery_mode` and `trigger_config_name`. Both set `connection="ConnectorNamespace"`.

The combined trigger stays enabled by default; separate row operations are opt-in
and overlap its events. The deprecated List rows HTTP action stays removed. Use
the organization's HTTPS URL, a **logical table name** such as `account` for combined
events, and the distinct **entity-set name** `accounts` for separate row operations.

This refresh follows reference PR 13 at `95fe5d933dea83620e84c627af098eed72575e85`.
It ports event selection, system identities, state reconciliation, and scoped action
cleanup; .NET startup, NuGet, and MSBuild changes have no Python counterpart.

Each app includes independent infrastructure, dependencies, hooks, and safe local
settings examples. Run `azd up` from the chosen folder with a separate environment
name for each mode. Poll delivery does not require a public callback; webhook
delivery uses the connector extension system key.

Python 3.13+ requires `azure-functions>=2.4.0b1`; older supported Python versions
require `azure-functions>=1.27.0b1` and `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`.
Requirements use version markers. Templates use Python 3.14 and include isolation.
Both apps retain `azurefunctions-extensions-connectors>=1.0.0b4`.

See the [Dataverse connector reference](https://learn.microsoft.com/connectors/commondataservice/).