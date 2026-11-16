# Office 365 Outlook polling triggers (Python)

The Functions host receives events from the Connector Namespace polling endpoint. Six personal-mailbox/calendar sources are enabled by default; shared-mailbox email is opt-in. No public callback is required.

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

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- An Office 365 mailbox/calendar and an account permitted to authorize the connection and manage trigger configurations.
- A supported Python version; the template deploys Python 3.14. Hooks also require Python; set `PYTHON` to an interpreter path if needed. Use PowerShell or a POSIX shell.
- For local runs, [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0b1` for Python 3.13+ or `azure-functions>=1.27.0b1` for older supported versions, and `azurefunctions-extensions-connectors>=1.0.0b4`. The requirements file selects the SDK family.

For Python 3.12 and older, set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it. Install the version-specific packages from `requirements.txt`.

## Deploy to Azure

```bash
az login
azd auth login
azd env new office365-polling
azd up
```

Authorize with the mailbox account, then select a mail folder and calendar from the connector's choices. The hook preserves existing consent and saves the selections in the azd environment. It creates enabled Poll configs after consent, provisions the Function App using their polling endpoint, and deploys the code. Reruns preserve unrelated Function App settings while refreshing the sample-managed settings.

## Optional configuration

| Setting or action | Purpose |
| --- | --- |
| `OFFICE365_MAIL_FOLDER` | Skip the folder picker with `Inbox` or a connector-returned folder ID. |
| `OFFICE365_CALENDAR_ID` | Skip the calendar picker with a connector-returned calendar ID. |
| `OFFICE365_SHARED_MAILBOX_ADDRESS` | Enable shared-mailbox email; the account needs full mailbox access. Empty by default. |
| `OFFICE365_SHARED_MAILBOX_FOLDER_ID` | Skip the shared-mailbox folder picker with a connector-returned folder ID. |
| `CONNECTOR_NAMESPACE_LOCATION`, `APPLICATION_INSIGHTS_LOCATION` | Override the namespace or monitoring region. |
| `azd hooks run postdeploy` | Rerun setup while preserving existing local settings. |

After changing source parameters, run `azd up`. Clearing the shared mailbox address disables an existing sample-owned shared Poll config without deleting it. To inspect consent without writing settings or triggers, run `python ./infra/scripts/setup.py --mode polling --project . --consent-link-only` after provisioning the base layer.

## Local development

Start Azurite separately. After provisioning, run:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
az login
azd hooks run postdeploy
func start
```

The hook creates local settings with the endpoint, trigger names, and listener flags if absent. To replace an existing file, run `pwsh ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` or `sh ./infra/scripts/postdeploy.sh --force-local-settings`. Use developer credentials locally and update listener flags when changing the selected sources. Stop the deployed app or use separate configs to avoid competing listeners.

## Verify and clean up

Check Connected consent and enabled Poll configs in [Connector Namespaces](https://connectors.azure.com/). Generate the selected mail/calendar events and check `Received <FunctionName> trigger (<Count> items)` logs. Source detection can be delayed and delivery can repeat. The handlers log counts, not message content.

Run `azd down --purge` from this folder when finished. Never commit credentials or local settings.
