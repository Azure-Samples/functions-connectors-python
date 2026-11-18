# Microsoft Teams webhook triggers (Python)

The Connector Namespace calls the deployed function's connector callback when Teams events occur. Four typed events are enabled by default; seven raw-string events are opt-in.

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

Handlers log event names and item counts, not content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- PowerShell 7.3+ (`pwsh`) on every platform, used by the deployment hooks.
- A Teams account with access to the team and channel you want to monitor. Optional events may need extra scopes, licenses, or policies.
- For local runs: Python, [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local), and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app deploys on Python 3.14. Locally, use Python 3.13 or newer; for 3.12 and older, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```powershell
az login
azd auth login
azd env new teams-webhook
azd up
```

`azd up` asks you to:

1. Sign in to authorize the Teams connection.
2. Pick the team and channel, unless `TEAMS_GROUP_ID` (group object ID) and `TEAMS_CHANNEL_ID` (URL-decoded channel ID) are already set with `azd env set`.

Run `azd up` again to deploy code changes or to retry after a failure.

### Enable optional events

Copy entries from `infra/additional-triggers.example.json` into `infra/additional-triggers.json`, replace the placeholders with connector values (keep parameter casing and JSON types), then run `azd up`.

| Operation | Required parameters |
| --- | --- |
| [`WebhookChatMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-chat-message-is-added) | None; covers **all chats of the connected user**. |
| [`WebhookNewMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-message-is-added-to-a-chat-or-channel), [`WebhookAtMentionTrigger`](https://learn.microsoft.com/connectors/teams/#when-i'm-@mentioned) | `threadType` and dynamic `requestBody`. |
| [`WebhookKeywordTrigger`](https://learn.microsoft.com/connectors/teams/#when-keywords-are-mentioned) | `threadType`, `$search`, and dynamic `requestBody`. |
| [`WebhookMessageReactionTrigger`](https://learn.microsoft.com/connectors/teams/#when-someone-reacted-to-a-message-in-chat) | `reactionKey`, `frequency`, `runningPolicy`, `threadType`, and dynamic `requestBody`. |
| [`RecordingTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-recording-is-available), [`TranscriptTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-transcript-is-available) | `scopeType` and dynamic `body`; meeting policies and licenses apply. |

Removing an entry does not delete its trigger configuration; disable or delete it in [Connector Namespaces](https://connectors.azure.com/) to stop events.

## Local development

1. Run `azd up` first. It creates `local.settings.json` if absent (or copy `local.settings.example.json`). To regenerate it, run `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings`.
2. Start Azurite.
3. Install dependencies and start the host:

   ```powershell
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   func start --enableAuth
   ```

Deployed callbacks target Azure, not localhost. To receive events locally, expose the host through a secure HTTPS tunnel and register your own trigger configurations with the local `connector_extension` system key. Keep `--enableAuth`: Core Tools skips key checks without it. Run `azd up` to restore the deployed callbacks.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), confirm the connection is Connected and the trigger configurations are enabled.
2. Post a channel message, mention the connected user, or add and remove a test team member. Optional events need their own source actions.
3. Check the function logs for invocations and item counts.

## Deprovision

```powershell
azd down --purge
```

Never commit callback keys, credentials, or `local.settings.json`.
