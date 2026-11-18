# Office 365 Outlook polling triggers (Python)

The Functions host pulls mail and calendar events from the Connector Namespace, so the app needs no public endpoint.

| Function | Connector operation | Binding |
| --- | --- | --- |
| `OnNewEmail` | [`OnNewEmailV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-arrives-(v3)) | `List[office365.GraphClientReceiveMessage]` |
| `OnFlaggedEmail` | [`OnFlaggedEmailV4`](https://learn.microsoft.com/connectors/office365/#when-an-email-is-flagged-(v4)-(preview)) | `List[office365.GraphClientReceiveMessage]` |
| `OnNewMentionMeEmail` | [`OnNewMentionMeEmailV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-mentioning-me-arrives-(v3)) | `List[office365.GraphClientReceiveMessage]` |
| `OnNewCalendarEvent` | [`CalendarGetOnNewItemsV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-event-is-created-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnUpcomingEvent` | [`OnUpcomingEventsV3`](https://learn.microsoft.com/connectors/office365/#when-an-upcoming-event-is-starting-soon-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnCalendarUpdatedItems` | [`CalendarGetOnUpdatedItemsV3`](https://learn.microsoft.com/connectors/office365/#when-an-event-is-modified-(v3)) | `List[office365.GraphCalendarEventClientReceive]` |
| `OnSharedMailboxNewEmail` | [`SharedMailboxOnNewEmailV2`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-arrives-in-a-shared-mailbox-(v2)) | `List[office365.GraphClientReceiveMessage]` |

[`CalendarGetOnChangedItemsV3`](https://learn.microsoft.com/connectors/office365/#when-an-event-is-added,-updated-or-deleted-(v3)) is excluded because its preview subscription fails with missing `TABLE`.

Handlers log the function name and item count, not message or event content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python, used by the deployment hooks. Set `PYTHON` to an interpreter path if it isn't on `PATH`.
- An Office 365 mailbox and calendar. `OnSharedMailboxNewEmail` also needs full access to the shared mailbox.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app deploys on Python 3.14. Locally, use Python 3.13 or newer; for 3.12 and older, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new office365-polling
azd up
```

`azd up` asks you to:

1. Sign in with the mailbox account to authorize the Office 365 connection.
2. **Configure** or **Skip** each trigger. Configure at least one.
3. For each configured trigger, pick its inputs, such as mail folder, calendar, or shared mailbox, from live lists, or type them where no list exists. Optional filters can be skipped.

Skipped functions are still deployed with their listeners disabled.

Choices are reused by later `azd up` runs. To choose again, run `azd env set POLLING_TRIGGER_INPUTS ""`, then `azd up`.

To skip the prompts, create `trigger-inputs.json` in this folder: an array of `{ "functionName", "operationName", "parameters": [{ "name", "value" }] }` objects using connector parameter names.

Run `azd up` again to deploy code changes or to retry after a failure.

| Optional setting | Purpose |
| --- | --- |
| `OFFICE365_MAIL_FOLDER`, `OFFICE365_CALENDAR_ID` | Folder and calendar IDs to use instead of picking them. |
| `OFFICE365_SHARED_MAILBOX_ADDRESS`, `OFFICE365_SHARED_MAILBOX_FOLDER_ID` | Shared mailbox and folder to use instead of picking them. |

## Local development

1. Run `azd up` first. It creates `local.settings.json` if absent. To regenerate it, run `sh ./infra/scripts/configure-triggers.sh finish --force-local-settings` (or `./infra/scripts/configure-triggers.ps1` in PowerShell).
2. Start Azurite.
3. Install dependencies and start the host:

   ```bash
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   az login
   func start
   ```

The local host and the deployed app compete for the same events; stop the deployed app while testing locally.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), confirm the connection is Connected and the trigger configurations are enabled.
2. Send, flag, or @mention yourself in an email, or create or update a calendar event.
3. Check the function logs for `Received <FunctionName> trigger (<Count> items)`. Detection can be delayed, and events can be delivered more than once.

## Deprovision

```bash
azd down --purge
```

Never commit credentials or `local.settings.json`.
