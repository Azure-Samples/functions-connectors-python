# Office 365 Outlook triggers (Python)

Choose one of two apps. Both cover the same seven events.

| Sample | Delivery |
| --- | --- |
| [Polling](./polling/README.md) | The Functions host receives events from the Connector Namespace polling endpoint using Microsoft Entra credentials. No public callback is needed. |
| [Webhook](./webhook/README.md) | The Connector Namespace sends events to the Functions connector callback, authenticated with the extension system key. |

Each folder includes its own infrastructure, dependencies, deployment hooks, and `infra/scripts/setup.py`. No parent or sibling files are required. Run `azd up` from the folder you choose. Use different azd environment names if you deploy both apps, so they do not share or overwrite resources.

| Function | Connector operation | SDK binding |
| --- | --- | --- |
| `OnNewEmail` | [`OnNewEmailV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-arrives-(v3)) | `List[office365.GraphClientReceiveMessage]` |
| `OnFlaggedEmail` | [`OnFlaggedEmailV4`](https://learn.microsoft.com/connectors/office365/#when-an-email-is-flagged-(v4)-(preview)) | `List[office365.GraphClientReceiveMessage]` |
| `OnNewMentionMeEmail` | [`OnNewMentionMeEmailV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-mentioning-me-arrives-(v3)) | `List[office365.GraphClientReceiveMessage]` |
| `OnNewCalendarEvent` | [`CalendarGetOnNewItemsV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-event-is-created-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnUpcomingEvent` | [`OnUpcomingEventsV3`](https://learn.microsoft.com/connectors/office365/#when-an-upcoming-event-is-starting-soon-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnCalendarUpdatedItems` | [`CalendarGetOnUpdatedItemsV3`](https://learn.microsoft.com/connectors/office365/#when-an-event-is-modified-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnSharedMailboxNewEmail` | [`SharedMailboxOnNewEmailV2`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-arrives-in-a-shared-mailbox-(v2)) | `List[office365.GraphClientReceiveMessage]` (opt-in) |

Six personal-mailbox/calendar sources run by default. A nonempty `OFFICE365_SHARED_MAILBOX_ADDRESS` enables the seventh source; full mailbox access is required. Select the actual connector calendar ID rather than relying on the `Calendar` placeholder. New mail is not filtered by importance.

Do not register [`CalendarGetOnChangedItemsV3`](https://learn.microsoft.com/connectors/office365/#when-an-event-is-added,-updated-or-deleted-(v3)) (added, updated or deleted events): the preview subscription fails with missing `TABLE`. Deprecated versions are not included. [`CalendarGetOnUpdatedItemsV3`](https://learn.microsoft.com/connectors/office365/#when-an-event-is-modified-(v3)) is the supported modified-event operation, not a substitute name for the changed-items operation.

## Python dependencies

| Python | Minimum `azure-functions` | Required setting |
| --- | --- | --- |
| 3.13 and newer | `2.4.0` | None |
| 3.12 and older (supported Functions versions) | `1.27.0b1`, installed manually | `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` |

Requirements install the SDK only on Python 3.13+; on older versions, install it before the sample requirements. The deployment templates use Python 3.14. Both apps require `azurefunctions-extensions-connectors>=1.0.0`.

Handlers log only the function name and item count, not subjects, addresses, organizers, dates, attachments or body content. Delivery is at least once; add deduplication before using non-idempotent actions. Test with a test mailbox and delete resources with `azd down --purge` when finished.

## References

- [Office 365 Outlook connector](https://learn.microsoft.com/connectors/office365/)
- [Operations to Functions signature mapping](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md)