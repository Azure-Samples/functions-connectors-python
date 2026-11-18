# Microsoft Dataverse connector events (Python)

Use the [polling app](./polling/README.md) if the Functions host should pull events from the Connector Namespace without a public endpoint. Use the [webhook app](./webhook/README.md) if the namespace should call the deployed function. Both apps handle these events:

| Function | Operation | Event |
| --- | --- | --- |
| `OnDataverseRowChanged` | [`SubscribeWebhookTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-a-row-is-added,-modified-or-deleted) | Row added, modified, or deleted |
| `OnDataverseActionPerformed` | [`BusinessEventsTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-an-action-is-performed) | Selected action performed |
| `OnDataverseRowAdded` | `SubscribeOnNewItems` | Row added |
| `OnDataverseRowModified` | `SubscribeOnUpdatedItems` | Row modified |
| `OnDataverseRowDeleted` | `SubscribeOnDeletedItems` | Row deleted |

See the [Dataverse connector reference](https://learn.microsoft.com/connectors/commondataservice/).
