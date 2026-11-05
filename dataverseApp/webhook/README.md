# Microsoft Dataverse webhook events (Python)

This app covers `OnDataverseRowChanged` (`SubscribeWebhookTrigger`), opt-in
`OnDataverseActionPerformed` (`BusinessEventsTrigger`), and separate row functions
`OnDataverseRowAdded` (`GetOnNewItems_V2`), `OnDataverseRowModified`
(`GetOnUpdatedItems_V2`), and `OnDataverseRowDeleted` (`GetOnDeletedItems_V2`).
All use raw `str` payloads: the Python extension has no matching Dataverse models.
The port does not invent SDK types. They log only trigger names;
their bodies match the [polling app](../polling).

## Prerequisites

- Azure Developer CLI, Azure CLI 2.75.0+, and the
  [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- **PowerShell 7.3+**, including when using the Bash wrapper.
- A Dataverse organization and an OAuth account permitted to register
  organization-scoped event subscriptions.
- A supported Python version; deployment uses Python 3.14. Requirements select
  `azure-functions>=2.4.0b1` for Python 3.13+ and `azure-functions>=1.27.0b1` for
  older supported versions. Python 3.12 and older need
  `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, included in deployed and local settings.
- `azurefunctions-extensions-connectors>=1.0.0b4`.

## Deploy

From the repository root:

```powershell
cd dataverseApp/webhook
az login
azd auth login
azd env new dataverse-webhook
azd env set DATAVERSE_ENVIRONMENT_URL https://contoso.crm.dynamics.com
azd up
```

Use a different environment name from polling. Supply the organization's HTTPS URL,
not a friendly name. `DATAVERSE_TABLE_NAME` defaults to the logical name `account`,
**not** the plural entity set `accounts`. Row events use `organization`, `entityname`,
`message=7` (added, modified, or deleted), and organization scope `scope=4`.

Deployment creates a Python 3.14 Linux Flex Consumption app, host storage,
monitoring, system-assigned identities, a Connector Namespace, and an OAuth connection. Set
`TELEMETRY_LOCATION` if monitoring needs a different region.
`CONNECTOR_NAMESPACE_LOCATION` defaults to `westcentralus`.

The app's system identity uses host Blob Data Owner, Queue Data Contributor, and
Table Data Contributor roles, `SystemAssignedIdentity` deployment storage, and
Monitoring Metrics Publisher with `Authorization=AAD`. Function access and roles
are assigned after app creation to avoid storage/app cycles. There is no deployed
`FUNCTIONS_WORKER_RUNTIME` on Flex; Bicep selects Python 3.14.

The hook authorizes the connection and registers selected current-event Webhook
configs through ARM (`Push` delivery). It discovers the actual Function App hostname
and uses its **connector extension system key**, not an ordinary function key.
Registration errors fail the hook, and temporary callback files are cleaned up.
Existing resources must match the sample's name, identity, connection, connector,
operation, and delivery mode before the hook changes them.

### Optional action-performed event

Before `azd up`, set `DATAVERSE_ENABLE_ACTION_TRIGGER=true` and all four actual
selector identifiers: `DATAVERSE_EVENT_CATALOG`, `DATAVERSE_EVENT_CATEGORY`,
`DATAVERSE_EVENT_TABLE`, and `DATAVERSE_EVENT_ACTION`. The last maps to
`sdkmessagename`; these are event-selector values, not display labels or placeholders.
Preprovision validation rejects incomplete configuration.

Action-performed is disabled by default. To turn it off, set the flag to `false`
and rerun `azd up`. This disables the function and removes only a matching
sample-owned action subscription; unrelated registrations are preserved.

### Optional separate row operations

Set `DATAVERSE_ENABLE_SEPARATE_ROW_TRIGGERS=true` and
`DATAVERSE_ENTITY_SET_NAME=accounts` before `azd up` to subscribe all three separate
row functions. They use `dataset` and plural entity-set `table`, not the combined
operation's logical `entityname`. Events overlap combined row delivery. All four
optional functions are disabled in public local examples. Turning the flag off
removes only matching owned separate-row namespace configs.

### Action subscription cleanup

Before action creation or namespace deletion, the helper writes a private ignored
`.azure/dataverse-action-cleanup-*.json` journal bound to the namespace, connection,
app, organization, delivery mode, operation, function, and selectors. An enabled
owned action with the same selectors is preserved, not re-registered. Selector
drift, disabled existing actions, foreign ownership, and ambiguous configs fail closed.
Provider callback query redaction is accepted only with exact destination metadata.
Legacy configs without that metadata require manual ownership checks.

Disabling the action removes only its Connector Namespace config, then **fails**
while source cleanup remains unverified. Reruns keep failing and the journal blocks
replacement creation. Inspect Dataverse for the exact owned `callbackregistration`,
verify its selectors and destination, remove only it, and confirm GET returns 404.
Only then archive the matching journal outside this app and rerun. Do not bulk-delete
by catalog, category, message, or table; preserve other subscriptions. No script
automatically deletes Dataverse callbacks. The helper accepts explicit trigger and
function names for another action config; use a separate journal path per config.

The hook generates safe local settings atomically only when missing, preserving
existing files and Connected OAuth consent. Rerun with `azd hooks run postdeploy`.
After changing event selection, explicitly regenerate local settings with
`pwsh ./infra/scripts/postdeploy.ps1 -ForceLocalSettings`. The Bash wrapper accepts
the same switch and still requires PowerShell 7.

## Run locally

Install requirements in a virtual environment and install Functions Core Tools v4
and Azurite. Use the generated local settings or copy `local.settings.example.json`
to `local.settings.json`. Start Azurite separately, then run `func start --enableAuth`.

Real local webhook delivery requires a secure public HTTPS tunnel and callback
configs targeting the local functions, authenticated with the local connector
extension system key. Core Tools bypasses local key checks unless `--enableAuth`
is set; enable it before exposing a tunnel. The deployment hook targets Azure, not localhost. Use separate
configs, or rerun the hook to restore deployed callbacks after manual changes.
The polling sample does not need a public tunnel.

## Verify and clean up

In [Connector Namespaces](https://connectors.azure.com/), verify Connected consent,
Enabled selected configs, and successful source registration. An Enabled resource
alone does not prove event registration succeeded. Create, modify, and delete a
test row, then check logs for `Received OnDataverseRowChanged trigger`. Optional
action delivery requires executing the selected action and has not been live-verified.

Never commit callback keys, tokens, or private local settings. Run
`azd down --purge` from this folder only after completing action source cleanup.