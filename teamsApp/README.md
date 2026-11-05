# Microsoft Teams connector events (Python)

Choose a standalone [polling app](./polling/README.md) or
[webhook app](./webhook/README.md). Both cover the eleven events in the
[.NET reference](https://github.com/Azure-Samples/functions-connectors-net/pull/11).
Infrastructure and hook behavior follow reference commit
`ca1f8cacfaa5f22e51ce2693c059a515f60acef5`, including its Poll deselection safeguards.
Python keeps its own SDK bindings, dependency markers, and native platform telemetry;
the .NET package and worker telemetry changes do not apply.

| Function / connector operation | Payload | Default |
| --- | --- | --- |
| `OnNewChannelMessage` | `list[teams.ChatMessage]` | Enabled |
| `OnNewChannelMessageMentioningMe` | `list[teams.ChatMessage]` | Enabled |
| `OnGroupMembershipAdd` | `list[teams.OnGroupMemberChangeResponse]` | Enabled |
| `OnGroupMembershipRemoval` | `list[teams.OnGroupMemberChangeResponse]` | Enabled |
| `WebhookChatMessageTrigger` | `str` | Opt-in |
| `WebhookNewMessageTrigger` | `str` | Opt-in |
| `WebhookAtMentionTrigger` | `str` | Opt-in |
| `WebhookKeywordTrigger` | `str` | Opt-in |
| `WebhookMessageReactionTrigger` | `str` | Opt-in |
| `RecordingTrigger` | `str` | Opt-in |
| `TranscriptTrigger` | `str` | Opt-in |

The four typed handlers log trigger names and actual item counts. Membership items
are SDK dictionary aliases. The seven raw-string handlers have no supported
callback models and log only event names: no payload parsing, guessed counts, or
message, member, recording, or transcript contents. A `Webhook` prefix in an
operation name describes the source subscription, not Functions delivery mode.

Handler code matches across delivery modes; polling adds only `delivery_mode` and
`trigger_config_name`. Both use `connection="ConnectorNamespace"`. Each folder has
independent infrastructure, dependencies, hooks, and safe local settings examples.
Run `azd up` from the chosen folder with a separate environment name for each mode.

Python 3.13+ requires `azure-functions>=2.4.0b1`; older supported Python versions
require `azure-functions>=1.27.0b1` and `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`.
Requirements use version markers and include `azurefunctions-extensions-connectors>=1.0.0b4`.
Deployment uses Python 3.14. PowerShell 7.3+ is required for setup on all platforms,
including the alternative Bash entry points.

See the [Teams connector reference](https://learn.microsoft.com/connectors/teams/).