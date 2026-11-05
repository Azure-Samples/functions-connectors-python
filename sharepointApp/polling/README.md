# SharePoint Online polling triggers (Python)

This app receives the [ten SharePoint events](../README.md) through Connector
Namespace Poll delivery. It needs no public callback, tunnel, or system key.
The five standard events run by default; the index lists the deletion, form,
Syntex, and digest prerequisites and optional environment settings.

## Deploy

Install Azure CLI 2.75.0+, Azure Developer CLI, and the
[connector-namespace CLI extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
From this folder, sign in with `az login` and `azd auth login`, create an environment
with `azd env new sharepoint-polling`, set `SHAREPOINT_SITE_URL` with `azd env set`,
then run `azd up`. The library defaults to `Documents`. Use a different environment
from the webhook app.

Bicep creates only selected Poll trigger configs and emits all ten names and
listener flags. Logical IDs retain the Python names, including
`sharepoint-onsharepointnewfile` and `sharepoint-onsharepointupdatedfile`.
Each handler adds `delivery_mode=func.DeliveryMode.POLL` and
`trigger_config_name="%<FunctionName>TriggerConfigName%"` to the webhook decorator.
Both use `connection="ConnectorNamespace"`.

The app uses system-assigned identity, managed-identity storage and connection
credentials, and the service-derived `ConnectorNamespace__pollingEndpoint`.
The hook preserves existing OAuth consent, or requests a bounded interactive
authorization. Sign in with an account that meets the selected source requirements.
Re-run with `azd hooks run postdeploy`. The hook never upserts enabled Poll configs;
Bicep owns them. It disables unselected existing sources by changing only state.

## Run locally

Create and activate a Python virtual environment, install the requirements with
`python -m pip install -r requirements.txt`, and sign in with `az login`.
Start Azurite and install Functions Core Tools. Run the hook after provisioning
to generate ignored local settings, then run `func start`. The settings contain
the deployed polling endpoint, all ten trigger names, and the selected listener
flags. Existing files are preserved; use `-ForceLocalSettings` or
`--force-local-settings` only when you want to replace them.

To generate settings without changing resources or requesting consent, invoke
the PowerShell hook with `-LocalSettingsOnly` or Bash hook with
`--local-settings-only`. `-ConsentLinkOnly` / `--consent-link-only` prints a consent
link without opening a browser or waiting. Bash hooks require Bash and Python,
not jq or PowerShell. No credentials are required merely to import the helper.

Use a separate environment for local tests, or stop the deployed app first:
hosts sharing trigger configs compete for events. Copying the example settings
is also supported; replace the polling endpoint placeholder and select flags.
Do not copy deployed credential/client-ID settings locally.

## Verify and clean up

Check that the connection is Connected and selected trigger configs are Enabled
with Poll delivery. Create and modify files and list items, then check logs for
the matching `OnSharepoint...` name and batch count. Updated-file events may also
fire on creation. Check optional events only after meeting their prerequisites.
Remove an opt-in, run `azd up`, and verify its source is Disabled, not deleted.
Run `azd down --purge` from this folder when finished.