# Office 365 Outlook polling triggers (Python)

This app handles the [seven supported events](../README.md). Six personal sources
are enabled by default; shared-mailbox email is opt-in. The host receives and
acknowledges events outbound from the Connector Namespace. No public callback,
connector system key or tunnel is needed.

## Prerequisites

- Python 3.14 for the deployed app and a Python interpreter for deployment hooks.
  The [dependency markers and language differences](../README.md) also describe
  supported older Python versions. Set `PYTHON` to an interpreter path if needed.
- Azure Developer CLI, Azure CLI 2.75.0+, and the `connector-namespace` CLI extension.
  Sign in with permission to read and update trigger configurations through ARM.
- PowerShell or a POSIX shell. Keep `../scripts/setup.py` with the checkout.
- Office 365 test mailbox/calendar; Functions Core Tools v4 and Azurite for local work.

## Deploy and choose sources

```bash
cd office365App/polling
az login
azd auth login
azd env new office365-polling
azd env set OFFICE365_MAIL_FOLDER Inbox
azd env set OFFICE365_CALENDAR_ID '<actual connector calendar ID>'
azd up
```

Use a different azd environment name from webhook. Infrastructure creates Python
3.14 on Linux FC1 with system-assigned identity, identity-based host/deployment
storage, telemetry, the namespace/connection and Poll trigger configurations.
Granting app RBAC after app creation avoids a settings/identity dependency cycle.

| Environment value | Default / purpose |
| --- | --- |
| `OFFICE365_MAIL_FOLDER` | `Inbox`; applies to personal email sources, without an importance filter |
| `OFFICE365_CALENDAR_ID` | `Calendar` placeholder; supply the actual connector calendar ID |
| `OFFICE365_SHARED_MAILBOX_ADDRESS` | Empty; opt in with a mailbox to which the authorized account has full access |
| `OFFICE365_SHARED_MAILBOX_FOLDER_ID` | `Inbox` |
| `OFFICE365_ENABLE_TRIGGERS` | `true`; set `false` to provision disabled sources without waiting for consent |
| `CONNECTOR_NAMESPACE_LOCATION` | `westcentralus` |
| `APPLICATION_INSIGHTS_LOCATION` | Host region; override if telemetry is unavailable there |

The hook preserves existing OAuth consent. Otherwise authorize with the mailbox
account using its consent link. `-ConsentLinkOnly` / `--consent-link-only` prints
the link, or reports existing consent, without opening a browser, waiting, or
writing local settings or triggers. Authorization waits at most five minutes.
If the connection is not authorized and sources are Disabled, the hook prints
the link and defers setup without waiting. After consent, rerun the hook without
the link-only flag to finish setup.

## Poll settings and lifecycle

`ConnectorNamespace__pollingEndpoint` comes from the service's receive URI with
its trigger path, query and optional `/api` suffix removed. Cloud settings use
`ConnectorNamespace__credential=managedidentity` without a user-assigned client ID.
All seven decorators use `%<FunctionName>TriggerConfigName%` with config names
`office365-<lowercase-function-name>`. The shared listener is disabled while its
mailbox address is empty; its name setting still exists.

After changing source parameters, run `azd provision` and the postdeploy hook.
If the shared address becomes empty, the hook disables an existing sample-owned
shared Poll source. It reads the full resource, checks scope, operation, connection
and delivery mode, removes read-only fields, and changes only `state`. It preserves
parameters, recurrence, metadata, description and other writable properties.
Absent or already-disabled shared configs are write no-ops. Personal Poll configs
are not rewritten by the hook. Incremental Bicep provisioning does not delete old
configs automatically; review resource ownership before any manual deletion.

## Local development

```bash
python -m venv .venv
# Activate the virtual environment for your shell.
python -m pip install -r requirements.txt
az login
azd hooks run postdeploy
# Start Azurite in another terminal.
func start
```

The hook creates ignored local settings using Azurite, Python, isolation `1`, the
deployed polling endpoint and all config names. Existing bytes are preserved,
including custom settings. To replace them deliberately, use
`pwsh ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` or
`sh ./infra/scripts/postdeploy.sh --force-local-settings`. This replaces the whole
file with explicit defaults; it does not merge private settings. Links/directories
are rejected, installation is atomic and owned staging files are cleaned.

Do not put cloud managed-identity credentials/client IDs in local settings. Local
execution uses developer authentication; the deploying user has connection access.
Stop the cloud app while testing its configs locally, or use separate resources:
otherwise hosts compete for the same events. Match the shared listener's disabled
setting to the selected mailbox when preserving an existing local file.

## Verify and clean up

Check **Connected**, enabled selected sources and **Poll** delivery in the Connector
Namespaces portal. Send mail of any importance, flag a message, mention yourself,
create/modify a calendar event, and create one starting soon. If opted in, send
shared-mailbox mail. Check `Received <FunctionName> trigger (<Count> items)` logs.
Source detection can be delayed; delivery is at least once. See the [excluded
changed-items preview operation](../README.md) before adding another calendar source.
No live delivery is implied by offline tests. Run `azd down --purge` when finished.