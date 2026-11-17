# Microsoft Teams connector events (Python)

Choose a standalone [polling app](./polling/README.md) or [webhook app](./webhook/README.md). Both cover the eleven events below.

| Function / connector operation | Payload | Default |
| --- | --- | --- |
| [`OnNewChannelMessage`](https://learn.microsoft.com/connectors/teams/#when-a-new-channel-message-is-added) | `List[teams.ChatMessage]` | Enabled |
| [`OnNewChannelMessageMentioningMe`](https://learn.microsoft.com/connectors/teams/#when-i-am-mentioned-in-a-channel-message) | `List[teams.ChatMessage]` | Enabled |
| [`OnGroupMembershipAdd`](https://learn.microsoft.com/connectors/teams/#when-a-new-team-member-is-added) | `List[teams.OnGroupMemberChangeResponse]` | Enabled |
| [`OnGroupMembershipRemoval`](https://learn.microsoft.com/connectors/teams/#when-a-new-team-member-is-removed) | `List[teams.OnGroupMemberChangeResponse]` | Enabled |
| [`WebhookChatMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-chat-message-is-added) | `str` | Opt-in |
| [`WebhookNewMessageTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-new-message-is-added-to-a-chat-or-channel) | `str` | Opt-in |
| [`WebhookAtMentionTrigger`](https://learn.microsoft.com/connectors/teams/#when-i'm-@mentioned) | `str` | Opt-in |
| [`WebhookKeywordTrigger`](https://learn.microsoft.com/connectors/teams/#when-keywords-are-mentioned) | `str` | Opt-in |
| [`WebhookMessageReactionTrigger`](https://learn.microsoft.com/connectors/teams/#when-someone-reacted-to-a-message-in-chat) | `str` | Opt-in |
| [`RecordingTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-recording-is-available) | `str` | Opt-in |
| [`TranscriptTrigger`](https://learn.microsoft.com/connectors/teams/#when-a-transcript-is-available) | `str` | Opt-in |

Handlers log trigger names and item counts, not message, member, recording, or transcript contents.

Each folder has independent infrastructure, dependencies, hooks, and local settings examples. Run `azd up` from the chosen folder with a separate environment name for each mode.

Python 3.13+ requires `azure-functions>=2.4.0`. On Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before the sample requirements and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; requirements install the SDK only on Python 3.13+. Requirements include `azurefunctions-extensions-connectors>=1.0.0`. Deployment uses Python 3.14. PowerShell 7.3+ is required for setup on all platforms.

See the [Teams connector reference](https://learn.microsoft.com/connectors/teams/).