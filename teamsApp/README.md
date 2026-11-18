# Microsoft Teams connector events (Python)

Choose the [polling app](./polling/README.md) (no public endpoint; the host pulls events) or the [webhook app](./webhook/README.md) (the Connector Namespace calls the deployed function). Both cover these events:

| Function / connector operation | Payload |
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

Each folder is a standalone app; run `azd up` from it, using a separate azd environment per app. See the [Teams connector reference](https://learn.microsoft.com/connectors/teams/).
