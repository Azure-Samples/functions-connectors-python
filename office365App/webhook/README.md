# Office 365 Outlook webhook triggers (Python)

Connector Namespace sends events to the Functions connector callback, authenticated with the `connector_extension` system key. Six personal-mailbox/calendar sources are enabled by default; shared-mailbox email is opt-in.

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

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- An Office 365 mailbox/calendar and an account permitted to authorize the connection and manage trigger configurations.
- A supported Python version; the template deploys Python 3.14. Hooks also require Python; set `PYTHON` to an interpreter path if needed. Use PowerShell or a POSIX shell.
- For local runs, [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0` for Python 3.13+ and `azurefunctions-extensions-connectors>=1.0.0`.

For Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before installing `requirements.txt`, which does not install the older SDK, and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it.

## Deploy to Azure

```bash
az login
azd auth login
azd env new office365-webhook
azd env set OFFICE365_MAIL_FOLDER Inbox
azd env set OFFICE365_CALENDAR_ID '<actual connector calendar ID>'
azd up
```

Authorize with the mailbox account when prompted. The hook preserves existing consent and registers selected callbacks using the deployed app's connector extension system key.

## Optional configuration

| Setting or action | Purpose |
| --- | --- |
| `OFFICE365_MAIL_FOLDER` | Personal email folder; defaults to `Inbox`. |
| `OFFICE365_CALENDAR_ID` | Actual connector calendar ID; replace the `Calendar` placeholder. |
| `OFFICE365_SHARED_MAILBOX_ADDRESS` | Enable shared-mailbox email; the account needs full mailbox access. Empty by default. |
| `OFFICE365_SHARED_MAILBOX_FOLDER_ID` | Shared mailbox folder; defaults to `Inbox`. |
| `OFFICE365_ENABLE_TRIGGERS` | Set `false` to skip the consent wait; defaults to `true`. After consent, rerun the hook to register disabled sources. |
| `CONNECTOR_NAMESPACE_LOCATION`, `APPLICATION_INSIGHTS_LOCATION` | Override the namespace or monitoring region. |
| `azd hooks run postdeploy` | Rerun setup while preserving existing local settings. |

Clearing the shared mailbox address disables its listener but does not disable or delete an existing shared webhook config; review and disable that config separately. Use `-ConsentLinkOnly` or `--consent-link-only` to obtain a consent link without writing settings or triggers, then rerun the hook after consent.

## Local development

- Start Azurite separately.
- Use the generated local settings or copy `local.settings.example.json` to `local.settings.json` if absent:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

- To receive local events, expose port 7071 through a secure public HTTPS tunnel and obtain the **local** `connector_extension` system key from Azurite's `azure-webjobs-secrets`.
- Core Tools bypasses key checks by default; enable authentication before exposing the host.

- Register the tunnel origin and local key with `pwsh ./infra/scripts/postdeploy.ps1 -CallbackBaseUrl <https-origin> -ConnectorExtensionKey <local-key>` or `sh ./infra/scripts/postdeploy.sh --callback-base-url <https-origin> --connector-extension-key <local-key>`.
- This replaces deployed callbacks; run `azd hooks run postdeploy` without overrides to restore them.
- Keep keys out of shell history, transcripts, and logs.

- The hook preserves existing local settings; use `-ForceLocalSettings` or `--force-local-settings` to replace them explicitly.
- Match the shared listener's disabled setting to your selected sources.

## Verify and clean up

Check Connected consent and enabled configs in [Connector Namespaces](https://connectors.azure.com/). Generate the selected mail/calendar events and check `Received <FunctionName> trigger (<Count> items)` logs. Source detection can be delayed and delivery can repeat. The handlers log counts, not message content.

Run `azd down --purge` from this folder when finished. Never commit callback keys, credentials, or local settings.
