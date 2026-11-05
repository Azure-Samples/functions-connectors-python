# Office 365 Outlook webhook triggers (Python)

This app handles the [seven supported events](../README.md) through the Functions
connector callback. Six personal sources are configured by default; shared-mailbox
email is opt-in. Source operations poll Office 365 even when namespace-to-host
delivery uses a webhook. Use [Poll delivery](../polling/README.md) to avoid a public
local callback.

## Prerequisites and deployment

Use Python 3.14, Azure Developer CLI, Azure CLI 2.75.0+, the `connector-namespace`
CLI extension, and an Office 365 test mailbox/calendar. Hooks run under PowerShell
or a POSIX shell and share `../scripts/setup.py`; keep that folder in the checkout.
Set `PYTHON` to an interpreter path if needed. No `jq` or .NET SDK is required.
See [Python dependencies and language differences](../README.md).

```bash
cd office365App/webhook
az login
azd auth login
azd env new office365-webhook
azd env set OFFICE365_MAIL_FOLDER Inbox
azd env set OFFICE365_CALENDAR_ID '<actual connector calendar ID>'
azd up
```

Use a different azd environment from polling. FC1 runs Python 3.14 with
system-assigned identity and identity-based host/deployment storage. Separate
function-access resources grant storage and telemetry RBAC after identity creation.
Incoming callbacks authenticate with the `connector_extension` **system key**,
not a function key, host key or the polling identity settings.

## Configuration and repeat runs

Set values before `azd up`: `OFFICE365_MAIL_FOLDER` (default `Inbox`),
`OFFICE365_CALENDAR_ID` (replace the `Calendar` placeholder),
`OFFICE365_SHARED_MAILBOX_ADDRESS` (empty by default),
`OFFICE365_SHARED_MAILBOX_FOLDER_ID` (default `Inbox`),
`CONNECTOR_NAMESPACE_LOCATION` (default `westcentralus`), and
`APPLICATION_INSIGHTS_LOCATION` (defaults to the host region).
The authorized account needs full access to an opted-in shared mailbox.

`OFFICE365_ENABLE_TRIGGERS=false` registers disabled sources without waiting for
consent. Set it back to `true` and run `azd up` to activate them. The hook preserves
existing OAuth consent, checks ownership before updating a config, uses the
deployed FQDN, and preserves custom recurrence and unrelated metadata. It registers
`<connection-name>-<lowercase-function-name>` configurations. Re-running the hook
updates callbacks; it does not create duplicate names.

Empty shared address disables the listener and skips registration. It does **not**
disable/delete a prior shared webhook source; review and disable that config
separately. Unlike Poll's state-only cleanup, webhook callback registration can
change delivery destinations. Keep local listener settings consistent with your
selection when preserving a local file.

`pwsh ./infra/scripts/postdeploy.ps1 -ConsentLinkOnly` or
`sh ./infra/scripts/postdeploy.sh --consent-link-only` skips browser opening and
authorization waiting, but still runs setup and callback updates. Normal consent
waiting is bounded to five minutes. CLI failures stop setup without printing key
or callback JSON bodies.

## Local settings and public tunnel

The hook creates ignored local settings for Azurite, Python and isolation `1`.
It preserves existing bytes. Explicitly replace the whole file with defaults using
`-ForceLocalSettings` / `--force-local-settings`; custom values are not merged.
Links/directories are rejected and writes are atomic. Cloud credentials and keys
never enter this generated file.

1. Create/activate a virtual environment and run `python -m pip install -r requirements.txt`.
2. Start Azurite, then `func start --enableAuth`. Core Tools normally bypasses
   local key authentication; enable it **before** exposing a public tunnel.
3. Expose port 7071 over public HTTPS. Read the local `connector_extension` system
   key from Azurite's `azure-webjobs-secrets`, not from the Azure app.
4. With the provisioned azd environment selected, invoke
   `pwsh ./infra/scripts/postdeploy.ps1 -CallbackBaseUrl <https-origin> -ConnectorExtensionKey <local-key>`
   or the shell options `--callback-base-url` and `--connector-extension-key`.
   Pass only an HTTPS origin without a path, query, credentials or fragment.
   Avoid shell history, transcripts and CI argument logging for the real key.
5. These overrides replace deployed callbacks. Restore Azure delivery with
   `azd hooks run postdeploy` without overrides when finished.

The Python handler receives a typed list from the extension converter. All seven
handlers log only event names/counts; they do not log mailbox or calendar content.
They do not copy .NET operation-envelope classes or worker telemetry startup.

## Verify and clean up

Check **Connected** and enabled selected sources in Connector Namespaces. Generate
new mail (any importance), flagged/mention mail, new/modified/upcoming calendar
events and optional shared-mailbox mail. Check `Received <FunctionName> trigger
(<Count> items)` logs. Source detection can be delayed and delivery is at least
once; build/deploy success does not prove event delivery. The changed-items preview
operation remains [excluded](../README.md). Delete test resources with
`azd down --purge` when finished.