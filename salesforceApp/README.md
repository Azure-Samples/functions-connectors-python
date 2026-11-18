# Salesforce connector samples (Python)

Choose [polling](polling/README.md) (the host pulls events; no public endpoint) or [webhook](webhook/README.md) (the Connector Namespace calls the deployed function). Each folder is a standalone app; use a separate azd environment for each. Both expose the same functions:

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnSalesforceNewItems` | [When a record is created](https://learn.microsoft.com/connectors/salesforce/#when-a-record-is-created) | `List[salesforce.Item]` |
| `OnSalesforceUpdatedItems` | [When a record is modified](https://learn.microsoft.com/connectors/salesforce/#when-a-record-is-modified) | `List[salesforce.Item]` |

See the [Salesforce connector reference](https://learn.microsoft.com/connectors/salesforce/) for operation details.
