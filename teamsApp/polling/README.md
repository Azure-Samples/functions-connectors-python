# Microsoft Teams polling triggers (Python)

The Functions host receives Teams events from the Connector Namespace polling endpoint. Four typed events are enabled by default; seven raw-string events require opt-in. No public callback is required.

| Function / connector operation | Binding | Selection |
| --- | --- | --- |
| [`OnNewChannelMessage`](https://learn.microsoft.com/connectors/teams/#when-a-new-channel-message-is-added) | `List[teams.ChatMessage]` | Default |
| [`OnNewChannelMessageMentioningMe`](https://learn.microsoft.com/connectors/teams/#when-i-am-mentioned-in-a-channel-message) | `List[teams.ChatMessage]` | Default |
| [`OnGroupMembershipAdd`](https://learn.microsoft.com/connectors/teams/#when-a-new-team-member-is-added) | `List[teams.OnGroupMemberChangeResponse]` | Default |
| [`OnGroupMembershipRemoval`](https://learn.microsoft.com/connectors/teams/#when-a-new-team-member-is-removed) | `List[teams.OnGroupMemberChangeResponse]` | Default |
| [`WebhookChatMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-chat-message-is-added) | `str` | Opt-in |
| [`WebhookNewMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-message-is-added-to-a-chat-or-channel) | `str` | Opt-in |
| [`WebhookAtMentionTrigger`](https://learn.microsoft.com/connectors/teams/#when-i'm-@mentioned) | `str` | Opt-in |
| [`WebhookKeywordTrigger`](https://learn.microsoft.com/connectors/teams/#when-keywords-are-mentioned) | `str` | Opt-in |
| [`WebhookMessageReactionTrigger`](https://learn.microsoft.com/connectors/teams/#when-someone-reacted-to-a-message-in-chat) | `str` | Opt-in |
| [`RecordingTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-recording-is-available) | `str` | Opt-in |
| [`TranscriptTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-transcript-is-available) | `str` | Opt-in |

Handlers log event names and typed counts, not customer content.

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- PowerShell 7.3+ and Python on every platform, including when using the Bash wrapper; set `PYTHON` to an interpreter path if needed.
- A Teams account with access to the selected team/channel and permission to authorize the connection. Optional events may require additional scopes, licenses, and policies.
- A supported Python version; the template deploys Python 3.14. For local runs, install [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0` for Python 3.13+ and `azurefunctions-extensions-connectors>=1.0.0`.

For Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before installing `requirements.txt`, which does not install the older SDK, and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it.

## Deploy to Azure

```powershell
az login
azd auth login
azd env new teams-polling
azd up
```

Authorize with the Teams account to monitor, then select a team and channel from the connector's choices. The hook saves their IDs in the azd environment. It creates enabled Poll configs after consent, provisions the Function App using their polling endpoint, and deploys the code. Reruns preserve unrelated Function App settings while refreshing the sample-managed settings.

## Optional configuration

Set `TEAMS_GROUP_ID` and `TEAMS_CHANNEL_ID` to connector-returned IDs before `azd up` to skip the pickers; use IDs, not display names. Set `CONNECTOR_NAMESPACE_LOCATION` or `TELEMETRY_LOCATION` to override the namespace or monitoring region. To enable optional events, copy selected entries from `infra/additional-triggers.example.json` into `infra/additional-triggers.json` and replace placeholders with actual connector values:

| Operation | Required parameters |
| --- | --- |
| [`WebhookChatMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-chat-message-is-added) | None; covers **all chats of the connected user**. |
| [`WebhookNewMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-message-is-added-to-a-chat-or-channel), [`WebhookAtMentionTrigger`](https://learn.microsoft.com/connectors/teams/#when-i'm-@mentioned) | `threadType` and dynamic `requestBody`. |
| [`WebhookKeywordTrigger`](https://learn.microsoft.com/connectors/teams/#when-keywords-are-mentioned) | `threadType`, `$search`, and dynamic `requestBody`. |
| [`WebhookMessageReactionTrigger`](https://learn.microsoft.com/connectors/teams/#when-someone-reacted-to-a-message-in-chat) | `reactionKey`, `frequency`, `runningPolicy`, `threadType`, and dynamic `requestBody`. |
| [`RecordingTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-recording-is-available), [`TranscriptTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-transcript-is-available) | `scopeType` and dynamic `body`; meeting policies and licenses apply. |

Preserve operation/parameter casing and JSON types. Run `azd up` to apply the selection. The hook disables deselected sample-owned optional Poll configs without deleting them; it does not prove upstream subscription teardown. Existing local settings are preserved. Use `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` to replace local settings after changing selection.

## Local development

Start Azurite separately. After provisioning, run:

```powershell
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
az login
azd hooks run postdeploy
func start
```

The hook creates local settings with the endpoint, trigger names, and listener flags if absent. Use developer credentials locally and update preserved flags after changing selections. Stop the deployed app or use separate trigger configs to avoid competing listeners.

## Verify and clean up

Check Connected consent, enabled configs, and successful source registration in [Connector Namespaces](https://connectors.azure.com/). Post a root channel message, mention the connection user, and add/remove a test team member. Check successful invocations and item counts; optional events require their selected source actions.

Disable or remove only your test subscriptions, then run `azd down --purge` from this folder. Never commit credentials or local settings.
