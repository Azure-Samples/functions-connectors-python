# Microsoft Teams polling events (Python)

This app covers all eleven events in the [Teams sample index](../README.md), with
four typed events configured by default. It receives and acknowledges events
through the Connector Namespace polling endpoint without a public callback or tunnel.

Typed handlers log `Received <FunctionName> trigger (<count> items)` using the
decoded list length. Raw-string handlers log only `Received <FunctionName> event`.
They do not parse payloads or log customer content. The [webhook app](../webhook)
has matching handler code; only the polling decorator arguments differ.

## Prerequisites

- Azure Developer CLI, Azure CLI 2.75.0+, and the
  [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- **PowerShell 7.3+ on every platform**, including for the Bash wrapper.
- A Teams account with team/channel access and permission to authorize the connection.
- A supported Python runtime; deployment uses Python 3.14. Requirements select
  `azure-functions>=2.4.0b1` on Python 3.13+, or `azure-functions>=1.27.0b1` on older
  supported versions, plus `azurefunctions-extensions-connectors>=1.0.0b4`.
- Python 3.12 and older require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, included in
  the deployed and local settings.

## Deploy

From the repository root:

```powershell
cd teamsApp/polling
az login
azd auth login
azd env new teams-polling
azd env set TEAMS_GROUP_ID "<team / Microsoft 365 group object ID>"
azd env set TEAMS_CHANNEL_ID "<URL-decoded channel ID>"
azd up
```

Replace both placeholders with IDs from a Teams channel link, not display names,
before provisioning. Use a different environment name from webhook. Sign in as the
Teams user to monitor when the OAuth hook opens the consent page. Connected consent
is preserved on reruns.

Deployment creates a Python 3.14 Linux Flex Consumption app, storage, system-assigned identities,
monitoring, a Connector Namespace, an OAuth connection, and selected Poll configs.
The function and developer connection policies allow event receipt. The host uses
`ConnectorNamespace__pollingEndpoint`, derived from the service receive URI, and
`ConnectorNamespace__credential=managedidentity`, without a client ID. After app
creation, a separate module grants its identity storage roles, Monitoring Metrics
Publisher, and connection access; storage provisioning does not depend on the app.
The namespace needs no separate connection access policy.

Native Functions platform telemetry uses `APPLICATIONINSIGHTS_CONNECTION_STRING`
and `APPLICATIONINSIGHTS_AUTHENTICATION_STRING=Authorization=AAD` with the app's
system-assigned identity. This Python sample adds no .NET worker telemetry setup.
Local settings omit Azure managed-identity and telemetry credentials.

`CONNECTOR_NAMESPACE_LOCATION` defaults to `westcentralus`; `TELEMETRY_LOCATION`
defaults to `eastus2` so telemetry can use a different supported region.
**No always-ready instances are configured**, matching the .NET reference.
Azure resources still incur charges; this sample does not claim idle listener readiness.

## Opt-in events

The checked-in `infra/additional-triggers.json` is `[]`. To select optional events,
copy entries from `infra/additional-triggers.example.json`, keep only authorized
events, and replace placeholders using actual values from the connector UI or an
exported configuration. Each entry has `functionName` and a `parameters` array:

| Operation | Required parameters |
| --- | --- |
| `WebhookChatMessageTrigger` | None; **all chats of the connected user**, not just the configured channel |
| `WebhookNewMessageTrigger`, `WebhookAtMentionTrigger` | `threadType`, dynamic `requestBody` |
| `WebhookKeywordTrigger` | `threadType`, `$search`, dynamic `requestBody` |
| `WebhookMessageReactionTrigger` | `reactionKey`, `frequency`, `runningPolicy`, `threadType`, dynamic `requestBody` |
| `RecordingTrigger`, `TranscriptTrigger` | `scopeType`, dynamic `body`; appropriate meeting policies and licenses |

Preserve canonical operation/parameter casing, JSON types, and nested values.
Targeted events require explicit `requestBody` even when a catalog marks it
optional. Broad chat and meeting scopes are never enabled implicitly. Hooks reject
unsupported or duplicate operations, invalid parameters, empty values, and placeholders;
the service validates dynamic schema values and permissions.

Run `azd up` to apply changes. Selected listeners are enabled automatically;
unselected listeners have `AzureWebJobs.<FunctionName>.Disabled=true`.
Postdeploy disables existing deselected configs only at the seven deterministic
sample-owned optional Poll IDs. Missing configs are skipped; default events and
unrelated configs are untouched. Conflicting delivery modes, operations, or
connections stop the hook. Reselecting an event re-enables the same ID through Bicep.
No configs are deleted. This changes config state, not upstream subscription
teardown or already queued events; it does not apply to webhook registrations.

Rerun setup with `azd hooks run postdeploy`. Local settings are written atomically
when missing and preserved byte-for-byte otherwise. Links and directories are rejected;
private staging files are cleaned on success and failure. After changing selection, update the local
disabled flags or run `pwsh -File ./infra/scripts/postdeploy.ps1 -ForceLocalSettings`
to regenerate settings deliberately. The Bash wrapper forwards the same switch.

## Run locally

Install Functions Core Tools v4 and Azurite. Use the generated local settings and
developer credentials, not deployed managed-identity settings:

```powershell
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt
az login
func start
```

Start Azurite separately first. If settings are missing, rerun the postdeploy hook
or copy `local.settings.example.json` and fill the endpoint and existing config names.
Enable only authorized, selected optional configs. `ConnectorNamespace` is a setting
prefix, not the source connection name. Derive its endpoint by removing the receive
operation, query, and `/triggerconfigs/<name>` path; retain any gateway path, or
strip a final `/api` from the base.

Stop the deployed app or use separate configs to avoid competing listeners. There
is no local connector emulator. Never commit tokens or private local settings.

## Verify and clean up

Check Connected consent, Enabled selected trigger configs, and successful source
registration in [Connector Namespaces](https://connectors.azure.com/). Post a new
root channel message, mention the connection user, and add/remove a test team member.
Check successful function invocations and genuine item counts, not just host startup.
Optional events need their corresponding source action, scopes, licenses, and permissions.

Delivery may repeat; the sample does not deduplicate. Disable or delete only your
test subscriptions and run `azd down --purge` from this folder when finished.