# Office 365 Outlook webhook triggers (Python)

The Connector Namespace calls the deployed function's connector callback when mail and calendar events occur. Six personal mailbox and calendar triggers are enabled by default; the shared-mailbox trigger is opt-in.

| Function | Connector operation | Binding | Selection |
| --- | --- | --- | --- |
| `OnNewEmail` | [`OnNewEmailV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-arrives-(v3)) | `List[office365.GraphClientReceiveMessage]` | Default |
| `OnFlaggedEmail` | [`OnFlaggedEmailV4`](https://learn.microsoft.com/connectors/office365/#when-an-email-is-flagged-(v4)-(preview)) | `List[office365.GraphClientReceiveMessage]` | Default |
| `OnNewMentionMeEmail` | [`OnNewMentionMeEmailV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-mentioning-me-arrives-(v3)) | `List[office365.GraphClientReceiveMessage]` | Default |
| `OnNewCalendarEvent` | [`CalendarGetOnNewItemsV3`](https://learn.microsoft.com/connectors/office365/#when-a-new-event-is-created-(v3)) | `List[office365.GraphCalendarEventClientReceive]` | Default |
| `OnUpcomingEvent` | [`OnUpcomingEventsV3`](https://learn.microsoft.com/connectors/office365/#when-an-upcoming-event-is-starting-soon-(v3)) | `List[office365.GraphCalendarEventClientReceive]` | Default |
| `OnCalendarUpdatedItems` | [`CalendarGetOnUpdatedItemsV3`](https://learn.microsoft.com/connectors/office365/#when-an-event-is-modified-(v3)) | `List[office365.GraphCalendarEventClientReceive]` | Default |
| `OnSharedMailboxNewEmail` | [`SharedMailboxOnNewEmailV2`](https://learn.microsoft.com/connectors/office365/#when-a-new-email-arrives-in-a-shared-mailbox-(v2)) | `List[office365.GraphClientReceiveMessage]` | Opt-in |

[`CalendarGetOnChangedItemsV3`](https://learn.microsoft.com/connectors/office365/#when-an-event-is-added,-updated-or-deleted-(v3)) is excluded because its preview subscription fails with missing `TABLE`.

Handlers log the function name and item count, not message or event content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python, used by the deployment hooks. Set `PYTHON` to an interpreter path if it isn't on `PATH`.
- An Office 365 mailbox and calendar. The shared-mailbox trigger also needs full access to the shared mailbox.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app deploys on Python 3.14. Locally, use Python 3.13 or newer; for 3.12 and older, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

1. Have the ID of the calendar to monitor, as accepted by the [Office 365 Outlook connector](https://learn.microsoft.com/connectors/office365/#when-a-new-event-is-created-(v3)). This is required: the default `Calendar` is a placeholder, not a real ID.
2. Create the environment, set the calendar ID, and deploy:

   ```bash
   az login
   azd auth login
   azd env new office365-webhook
   azd env set OFFICE365_CALENDAR_ID '<calendar ID>'
   azd up
   ```

3. When prompted, sign in with the mailbox account to authorize the Office 365 connection.

Run `azd up` again to deploy code changes, apply setting changes, or retry after a failure.

| Optional setting | Purpose |
| --- | --- |
| `OFFICE365_MAIL_FOLDER` | Personal mail folder. Defaults to `Inbox`. |
| `OFFICE365_SHARED_MAILBOX_ADDRESS` | Enables the shared-mailbox trigger. |
| `OFFICE365_SHARED_MAILBOX_FOLDER_ID` | Shared mailbox folder. Defaults to `Inbox`. |

Clearing the shared mailbox address disables its listener but not its trigger configuration; disable that in [Connector Namespaces](https://connectors.azure.com/).

## Local development

1. Run `azd up` first. It creates `local.settings.json` if absent (or copy `local.settings.example.json`). To regenerate it, run `sh ./infra/scripts/postdeploy.sh --force-local-settings` (or `./infra/scripts/postdeploy.ps1 -ForceLocalSettings` in PowerShell).
2. Start Azurite.
3. Install dependencies and start the host:

   ```bash
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   func start --enableAuth
   ```

Deployed callbacks target Azure, not localhost. To receive events locally:

1. Expose port 7071 through a secure HTTPS tunnel. Keep `--enableAuth`: Core Tools skips key checks without it.
2. Get the local `connector_extension` system key from Azurite's `azure-webjobs-secrets` container.
3. Point the callbacks at your tunnel: `sh ./infra/scripts/postdeploy.sh --callback-base-url <https-origin> --connector-extension-key <local-key>` (or `-CallbackBaseUrl` and `-ConnectorExtensionKey` with `postdeploy.ps1`). Keep the key out of shell history and logs.
4. Run `azd up` to restore the deployed callbacks when done.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), confirm the connection is Connected and the trigger configurations are enabled.
2. Send, flag, or @mention yourself in an email, or create or update a calendar event.
3. Check the function logs for `Received <FunctionName> trigger (<Count> items)`. Detection can be delayed, and events can be delivered more than once.

## Deprovision

```bash
azd down --purge
```

Never commit callback keys, credentials, or `local.settings.json`.
