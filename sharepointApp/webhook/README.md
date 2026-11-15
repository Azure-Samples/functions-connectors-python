# SharePoint Online webhook triggers (Python)

This app receives the same [ten SharePoint events](../README.md) and uses the same
typed handlers as the [polling app](../polling/README.md). Five standard events
run by default. See the index for source options and prerequisites for deletion,
form, Microsoft Syntex, and digest events.

## Deploy

Install Azure CLI 2.75.0+, Azure Developer CLI, and the
[connector-namespace CLI extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
From this folder, sign in with `az login` and `azd auth login`, create an environment
with `azd env new sharepoint-webhook`, set `SHAREPOINT_SITE_URL` with `azd env set`,
then run `azd up`. The library defaults to `Documents`. Use a different environment
from the polling app.

The template creates a Python 3.14 Linux Flex Consumption app with system-assigned
identity and identity-based storage. It configures all ten listener flags. The
post-deploy hook upserts selected sources, preserving recurrence and other writable
properties. It disables unselected existing sources rather than deleting them.
Existing connection consent remains intact; the hook requests authorization only
when needed. Sign in with an account that meets the selected source requirements.

Callback URLs use the deployed app's actual `functionAppDefaultHostname`, not an
assumed hostname. Authentication uses `systemKeys.connector_extension`, not a
host or function key. Logical IDs remain
`<connectionName>-onsharepoint<event>`. Private temporary JSON files carry keys
and request bodies and are removed after success or failure.

## Run locally

Create and activate a Python virtual environment, install requirements with
`python -m pip install -r requirements.txt`, start Azurite, and run `func start`.
The hook generates ignored local settings if absent and preserves existing files.
Use `-LocalSettingsOnly` (PowerShell) or `--local-settings-only` (Bash) to generate
settings without resource writes or consent. Use `-ForceLocalSettings` /
`--force-local-settings` to replace an existing file explicitly.

For live local delivery, use a public HTTPS tunnel and explicitly invoke the
post-deploy hook with `-CallbackBaseUrl` and `-ConnectorExtensionKey`, or the Bash
options `--callback-base-url` and `--connector-extension-key`. Supply the tunnel
origin only (no path, query, credentials, or fragment), and the **local** connector
extension key. Keep secrets out of shell history. Local overrides omit deployed
destination metadata and do not fetch a cloud key. Run the hook again without
these overrides to restore the deployed callback. Use the polling app to avoid
a public tunnel.

`-ConsentLinkOnly` / `--consent-link-only` prints the authorization link without
opening a browser, waiting, or writing local settings or trigger configs. If
already connected, it reports existing consent without writes. Do not combine
it with `--local-settings-only`. Rerun without the link-only flag after consent
to finish setup. Normal setup waits for OAuth before writing settings or triggers.
Both shells use one Python helper; Bash requires neither jq nor PowerShell.
Set `PYTHON` to the intended interpreter if needed.

## Verify and clean up

Check that the connection is Connected and selected sources are Enabled.
Create and modify files and list items, then check logs for the matching
`OnSharepoint...` name and batch count. Check optional events only after meeting
their prerequisites. Remove an opt-in, run `azd up`, and verify that both the
listener and source are disabled. Re-run hooks with `azd hooks run postdeploy`.
Do not commit private settings or keys. Run `azd down --purge` when finished.