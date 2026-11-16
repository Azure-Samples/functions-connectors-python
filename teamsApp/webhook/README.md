# Microsoft Teams webhook triggers (Python)

Connector Namespace sends Teams events to the Functions connector callback, authenticated with the `connector_extension` system key. Four typed events are enabled by default; seven raw-string events require opt-in.

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

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- PowerShell 7.3+ on every platform, including when using the Bash wrapper.
- A Teams account with access to the selected team/channel and permission to authorize the connection. Optional events may require additional scopes, licenses, and policies.
- A supported Python version; the template deploys Python 3.14. For local runs, install [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0` for Python 3.13+ and `azurefunctions-extensions-connectors>=1.0.0`.

For Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before installing `requirements.txt`, which does not install the older SDK, and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it.

## Deploy to Azure

```powershell
az login
azd auth login
azd env new teams-webhook
azd up
```

The hook authorizes the Teams connection and prompts for missing team/channel selections. Alternatively, set `TEAMS_GROUP_ID` to the group object ID and `TEAMS_CHANNEL_ID` to the URL-decoded channel ID before deployment. The hook registers callbacks using the deployed app's actual hostname and connector extension system key.

## Optional configuration

Set `CONNECTOR_NAMESPACE_LOCATION` or `TELEMETRY_LOCATION` to override the namespace or monitoring region. To enable optional events, copy selected entries from `infra/additional-triggers.example.json` into `infra/additional-triggers.json` and replace placeholders with actual connector values:

| Operation | Required parameters |
| --- | --- |
| [`WebhookChatMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-chat-message-is-added) | None; covers **all chats of the connected user**. |
| [`WebhookNewMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-message-is-added-to-a-chat-or-channel), [`WebhookAtMentionTrigger`](https://learn.microsoft.com/connectors/teams/#when-i'm-@mentioned) | `threadType` and dynamic `requestBody`. |
| [`WebhookKeywordTrigger`](https://learn.microsoft.com/connectors/teams/#when-keywords-are-mentioned) | `threadType`, `$search`, and dynamic `requestBody`. |
| [`WebhookMessageReactionTrigger`](https://learn.microsoft.com/connectors/teams/#when-someone-reacted-to-a-message-in-chat) | `reactionKey`, `frequency`, `runningPolicy`, `threadType`, and dynamic `requestBody`. |
| [`RecordingTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-recording-is-available), [`TranscriptTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-transcript-is-available) | `scopeType` and dynamic `body`; meeting policies and licenses apply. |

Preserve operation/parameter casing and JSON types. Run `azd up` to apply the selection. Removing an entry does not delete its existing namespace config; explicitly disable or delete the sample-owned source subscription to stop collection. Existing local settings are preserved; use `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` to replace them after changing selection.

## Local development

- Start Azurite separately.
- Use the generated local settings or copy `local.settings.example.json` to `local.settings.json` if absent:

```powershell
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

- To receive local events, expose the host through a secure public HTTPS tunnel and configure separate callbacks using the local function names and local `connector_extension` system key.
- Core Tools bypasses key checks by default; enable authentication before exposing the host.
- The hook targets Azure, not localhost; rerun it to restore deployed callbacks after manual changes.

## Verify and clean up

Check Connected consent, enabled configs, and successful source registration in [Connector Namespaces](https://connectors.azure.com/). Post a root channel message, mention the connection user, and add/remove a test team member. Check successful invocations and item counts; optional events require their selected source actions.

Disable or remove only your test subscriptions, then run `azd down --purge` from this folder. Never commit callback keys, credentials, or local settings.
