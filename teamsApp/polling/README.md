# Microsoft Teams polling triggers (Python)

The Functions host pulls Teams events from the Connector Namespace, so the app needs no public endpoint.

| Function / connector operation | Binding |
| --- | --- |
| [`OnNewChannelMessage`](https://learn.microsoft.com/connectors/teams/#when-a-new-channel-message-is-added) | `List[teams.ChatMessage]` |
| [`OnNewChannelMessageMentioningMe`](https://learn.microsoft.com/connectors/teams/#when-i-am-mentioned-in-a-channel-message) | `List[teams.ChatMessage]` |
| [`OnGroupMembershipAdd`](https://learn.microsoft.com/connectors/teams/#when-a-new-team-member-is-added) | `List[teams.OnGroupMemberChangeResponse]` |
| [`OnGroupMembershipRemoval`](https://learn.microsoft.com/connectors/teams/#when-a-new-team-member-is-removed) | `List[teams.OnGroupMemberChangeResponse]` |
| [`WebhookChatMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-chat-message-is-added) | `str` |
| [`WebhookNewMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-message-is-added-to-a-chat-or-channel) | `str` |
| [`WebhookAtMentionTrigger`](https://learn.microsoft.com/connectors/teams/#when-i'm-@mentioned) | `str` |
| [`WebhookKeywordTrigger`](https://learn.microsoft.com/connectors/teams/#when-keywords-are-mentioned) | `str` |
| [`WebhookMessageReactionTrigger`](https://learn.microsoft.com/connectors/teams/#when-someone-reacted-to-a-message-in-chat) | `str` |
| [`RecordingTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-recording-is-available) | `str` |
| [`TranscriptTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-transcript-is-available) | `str` |

Handlers log event names and item counts, not content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python, used by the deployment hooks.
- A Teams account with access to the team and channel you want to monitor. Optional events may need extra scopes, licenses, or policies.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app deploys on Python 3.14. Locally, use Python 3.13 or newer; for 3.12 and older, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new teams-polling
azd up
```

`azd up` asks you to:

1. Sign in to authorize the Teams connection.
2. **Configure** or **Skip** each trigger. Configure at least one.
3. For each configured trigger, pick its inputs, such as team and channel, from live lists, or type them where no list exists. Optional filters can be skipped.

Skipped functions are still deployed with their listeners disabled.

Choices are reused by later `azd up` runs. To choose again, run `azd env set POLLING_TRIGGER_INPUTS ""`, then `azd up`.

To skip the prompts, create `trigger-inputs.json` in this folder: an array of `{ "functionName", "operationName", "parameters": [{ "name", "value" }] }` objects using connector parameter names.

Run `azd up` again to deploy code changes or to retry after a failure.

| Optional setting | Purpose |
| --- | --- |
| `TEAMS_GROUP_ID`, `TEAMS_CHANNEL_ID` | Team and channel IDs to use instead of picking them. |

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
2. Post a channel message, mention the connected user, or add and remove a test team member. Optional events need their own source actions.
3. Check the function logs for invocations and item counts.

## Deprovision

```bash
azd down --purge
```

Never commit credentials or `local.settings.json`.
