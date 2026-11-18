# Office 365 Outlook triggers (Python)

Choose the [polling app](./polling/README.md) (no public endpoint; the host pulls events) or the [webhook app](./webhook/README.md) (the Connector Namespace calls the deployed function). Both cover these events:

| Function | Connector operation | SDK binding |
| --- | --- | --- |
| `OnNewEmail` | [`OnNewEmailV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-arrives-(v3)) | `List[office365.GraphClientReceiveMessage]` |
| `OnFlaggedEmail` | [`OnFlaggedEmailV4`](https://learn.microsoft.com/connectors/office365/#when-an-email-is-flagged-(v4)-(preview)) | `List[office365.GraphClientReceiveMessage]` |
| `OnNewMentionMeEmail` | [`OnNewMentionMeEmailV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-mentioning-me-arrives-(v3)) | `List[office365.GraphClientReceiveMessage]` |
| `OnNewCalendarEvent` | [`CalendarGetOnNewItemsV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-event-is-created-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnUpcomingEvent` | [`OnUpcomingEventsV3`](https://learn.microsoft.com/connectors/office365/#when-an-upcoming-event-is-starting-soon-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnCalendarUpdatedItems` | [`CalendarGetOnUpdatedItemsV3`](https://learn.microsoft.com/connectors/office365/#when-an-event-is-modified-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnSharedMailboxNewEmail` | [`SharedMailboxOnNewEmailV2`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-arrives-in-a-shared-mailbox-(v2)) | `List[office365.GraphClientReceiveMessage]` |

Delivery is at least once; add deduplication before taking non-idempotent actions.

Each folder is a standalone app; run `azd up` from it, using a separate azd environment per app. See the [Office 365 Outlook connector reference](https://learn.microsoft.com/connectors/office365/) and the [operations-to-Functions signature mapping](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md).
