# Microsoft Teams webhook events (Python)

This app covers all eleven events in the [Teams sample index](../README.md). Four
SDK-typed events are configured by default; seven raw-string events require opt-in
source scopes. Typed handlers log trigger names and actual decoded item counts;
raw handlers log only event names. No customer payload fields are logged.

The [polling app](../polling) has matching handler code. Webhook callbacks use the
connector extension system key; operation names prefixed `Webhook` can also be
used with Poll delivery and do not determine the Functions delivery mode.

## Prerequisites

- Azure Developer CLI, Azure CLI 2.75.0+, and the
  [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- **PowerShell 7.3+**, including when invoking the Bash wrapper.
- A Teams account with permission to access the selected team/channel and authorize
  the connection. Additional events may require meeting licenses and policies.
- A supported Python runtime; deployment uses Python 3.14. Requirements select
  `azure-functions>=2.4.0b1` on Python 3.13+, or `azure-functions>=1.27.0b1` for older
  supported versions, plus `azurefunctions-extensions-connectors>=1.0.0b4`.
- On Python 3.12 and older, `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, included in the
  deployed settings and local example.

## Deploy

From the repository root:

```powershell
cd teamsApp/webhook
az login
azd auth login
azd env new teams-webhook
azd up
```

Use a different environment name from polling. The hook authorizes the Teams
connection and prompts for missing team/channel selections. Alternatively set
`TEAMS_GROUP_ID` to the group object ID and `TEAMS_CHANNEL_ID` to the URL-decoded
channel ID before deployment. Display names are not IDs.

Deployment creates a Python 3.14 Linux Flex Consumption app, storage, system-assigned identities,
monitoring, a Connector Namespace, and an OAuth connection. The hook configures four
baseline subscriptions plus explicitly selected optional events, targeting the
actual Function App hostname. Callbacks authenticate with the **`connector_extension`
system key**, not an ordinary function key. Temporary callback files are cleaned up;
CLI failures stop setup without printing secret command output.

After app creation, a separate module grants its identity storage roles and
Monitoring Metrics Publisher, avoiding a storage/app dependency cycle. Webhook-only
reception needs no Function/developer or namespace connection access policy.
Native Functions platform telemetry uses `APPLICATIONINSIGHTS_CONNECTION_STRING`
and `APPLICATIONINSIGHTS_AUTHENTICATION_STRING=Authorization=AAD`; this Python
sample adds no .NET worker telemetry setup. Local settings omit Azure identity settings.

`CONNECTOR_NAMESPACE_LOCATION` defaults to `westcentralus`; `TELEMETRY_LOCATION`
defaults to `eastus2`. Rerun setup with `azd hooks run postdeploy`. Existing Connected
consent and local settings are preserved. Local settings use private atomic staging;
links and directories are rejected. To regenerate local settings after selection
changes, use `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings`.

## Opt-in events

`infra/additional-triggers.json` defaults to `[]`. Copy only authorized entries
from `infra/additional-triggers.example.json` and replace all placeholders:

| Operation | Required source parameters |
| --- | --- |
| `WebhookChatMessageTrigger` | None; **all chats of the connection user** |
| `WebhookNewMessageTrigger`, `WebhookAtMentionTrigger` | `threadType`, dynamic `requestBody` |
| `WebhookKeywordTrigger` | `threadType`, `$search`, dynamic `requestBody` |
| `WebhookMessageReactionTrigger` | `reactionKey`, `frequency`, `runningPolicy`, `threadType`, dynamic `requestBody` |
| `RecordingTrigger`, `TranscriptTrigger` | `scopeType`, dynamic `body`; appropriate meeting policies/licenses |

Use exact operation and parameter casing, actual source scopes/enums, and correct
JSON types. Do not copy tokens or keys. Validation rejects duplicates, unsupported
names, missing scopes, empty values, and placeholders. Broad chat or meeting scopes
are never enabled implicitly; the service validates the dynamic schema and permissions.

Run `azd up` to apply the selection. Unselected optional listeners are disabled.
Reruns update selected named registrations in place, without delete/recreate.
Removing an entry does **not** delete an existing ARM config: disable/delete the
sample-owned source subscription explicitly to stop collection. Update preserved
local disabled flags or regenerate settings after changing selection.

## Run locally

Create and activate a virtual environment and install requirements. Use generated
local settings, or copy `local.settings.example.json` if no private file exists.
Install Functions Core Tools v4 and Azurite; start Azurite separately and run
`func start --enableAuth` from this folder. Core Tools bypasses key authentication
locally by default; enable it before exposing a public tunnel.

Real local events require a secure public HTTPS tunnel and callback configs
targeting the local function names. Use the **local** connector extension system
key. The postdeploy hook registers Azure callbacks, not localhost. Use separate
configs or rerun the hook to restore deployed callbacks after manual changes.
The polling app avoids the need for a public tunnel.

## Verify and clean up

Check Connected consent, Enabled selected configs, and successful source registration
in [Connector Namespaces](https://connectors.azure.com/). Post a root channel message
(not a reply), mention the connection user, and add/remove a test member. Verify
successful invocations with trigger names and actual item counts. Optional events
require their corresponding action, source scope, and permissions.

Delivery may repeat; these samples do not deduplicate. Never commit tokens, callback
keys, or private settings. Disable/remove only test subscriptions and run
`azd down --purge` from this folder when finished.