# Microsoft Dataverse polling events (Python)

This app covers current row-change and opt-in action-performed events with the same
raw-string, trigger-name-only handlers as the [webhook app](../webhook). No public
callback, connector extension key, or local tunnel is needed.

| Function | Operation | Parameters |
| --- | --- | --- |
| `OnDataverseRowChanged` | `SubscribeWebhookTrigger` | `organization`, logical `entityname`, `message=7`, `scope=4` |
| `OnDataverseActionPerformed` | `BusinessEventsTrigger` | `organization`, `catalog`, `category`, `entityname`, `sdkmessagename` |
| `OnDataverseRowAdded` | `GetOnNewItems_V2` | `dataset`, entity-set `table` |
| `OnDataverseRowModified` | `GetOnUpdatedItems_V2` | `dataset`, entity-set `table` |
| `OnDataverseRowDeleted` | `GetOnDeletedItems_V2` | `dataset`, entity-set `table` |

All five handlers use native raw `str` bindings. The Python connector extension
does not expose the .NET Dataverse trigger models; this port does not invent SDK types.
The combined and action operations also lack matching typed models in the reference.

## Prerequisites

- Azure Developer CLI, Azure CLI 2.75.0+, and the
  [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- **PowerShell 7.3+ on every platform**, including when using the Bash wrapper.
- A Dataverse organization and permission to register organization-scoped event
  subscriptions. OAuth consent must use an account with those permissions.
- A supported Python version; deployment uses Python 3.14. Requirements select
  `azure-functions>=2.4.0b1` on Python 3.13+, or `azure-functions>=1.27.0b1` on older
  supported versions. Python 3.12 and older require
  `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, included in the templates and local settings.
- `azurefunctions-extensions-connectors>=1.0.0b4`.

## Deploy

From the repository root:

```powershell
cd dataverseApp/polling
az login
azd auth login
azd env new dataverse-polling
azd env set DATAVERSE_ENVIRONMENT_URL https://contoso.crm.dynamics.com
azd up
```

Use a different azd environment name from webhook. The default logical table is
`account`. Set `DATAVERSE_TABLE_NAME` to monitor another logical table—**not** its
plural entity-set name. The preprovision hook rejects missing or malformed
organization URLs and incomplete action selectors.

Deployment creates a Python 3.14 Linux Flex Consumption app, storage, monitoring,
system-assigned identities, a Connector Namespace, an OAuth connection, and selected Poll
trigger configs. Connection policies grant the app and developer access.
The host uses the service-derived `ConnectorNamespace__pollingEndpoint`,
`ConnectorNamespace__credential=managedidentity`, without a user-assigned client ID.
Each decorator resolves its `<FunctionName>TriggerConfigName` setting.

The template sets `alwaysReady: []`; it does not reserve billed idle instances.
Host storage uses the app's system identity and Blob Data Owner, Queue Data
Contributor, and Table Data Contributor roles. Deployment storage uses
`SystemAssignedIdentity`. The post-app role module avoids a storage/app dependency
cycle. Monitoring uses `Authorization=AAD` and Monitoring Metrics Publisher.

Set `TELEMETRY_LOCATION` to a supported monitoring region if unavailable in the
Function App region. `CONNECTOR_NAMESPACE_LOCATION` defaults to `westcentralus`.

### Optional action-performed event

Set all values before `azd up`:

| Environment setting | Value |
| --- | --- |
| `DATAVERSE_ENABLE_ACTION_TRIGGER` | `true` |
| `DATAVERSE_EVENT_CATALOG` | Actual catalog identifier |
| `DATAVERSE_EVENT_CATEGORY` | Actual category identifier |
| `DATAVERSE_EVENT_TABLE` | Table identifier accepted by the event selector |
| `DATAVERSE_EVENT_ACTION` | Actual SDK message name |

Do not use placeholder selector values. Action-performed is disabled by default
in the Functions app; no action configuration is created until enabled. The
postdeploy hook checks ownership and the cleanup journal before creating the
action configuration. Bicep does not create or update it. Reruns preserve matching
registrations and reject changed selectors before writing to the configuration.
Complete the source-cleanup steps below before replacing an action registration.
Set the enable flag to
`false` and rerun `azd up` to disable it. Incremental Bicep retains omitted configs;
the hook changes only the state of owned optional Poll configs. It retains the full
properties, selector values, metadata, and Poll delivery, then verifies state readback.
Foreign or ambiguous registrations stop the hook without being changed.

### Optional separate row operations

Set `DATAVERSE_ENABLE_SEPARATE_ROW_TRIGGERS=true` and
`DATAVERSE_ENTITY_SET_NAME=accounts` before provisioning. All three separate
operations use `dataset` and the plural entity-set name; the combined operation
still uses logical `DATAVERSE_TABLE_NAME=account`. Their events overlap combined
row changes. Both flags default to `false`; examples disable all four optional
functions. Turning separate rows off disables their existing Poll configs in place.

### Action subscription cleanup

The action helper writes a private, ignored `.azure/dataverse-action-cleanup-*.json`
journal bound to the exact namespace, connection, app, organization, delivery mode,
operation, function, and selectors. Keep it: disabling a Poll config does not prove
that Dataverse removed its source callback. The helper accepts explicit trigger and
function names for a separately managed action config; use a distinct journal path
for each such config and never reuse another registration's journal.

Before removing an action source subscription, identify its exact owned
`callbackregistration` in Dataverse, verify its selectors and destination, remove
only that registration, and confirm GET returns 404. Do not bulk-delete by table,
catalog, category, or message. Preserve unowned registrations and journals on any
failure. The scripts never automatically delete Dataverse callbacks. Missing old
metadata is not proof of ownership; inspect legacy registrations manually.

The OAuth hook preserves Connected consent and generates local settings atomically
when absent. Existing files are preserved. Rerun with `azd hooks run postdeploy`;
after changing event selection, use `pwsh ./infra/scripts/postdeploy.ps1 -ForceLocalSettings`
to regenerate local settings deliberately. The Bash wrapper forwards that switch
and still requires PowerShell 7.

## Run locally

Install Functions Core Tools v4 and Azurite. In this folder, create and activate a
virtual environment, install requirements, and sign in as the provisioned developer:

```powershell
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt
az login
azd hooks run postdeploy
func start
```

Start Azurite separately first. Use generated local settings with developer
credentials, not deployed managed-identity settings. The public example requires
the deployed polling endpoint. Stop the deployed app or use separate configs to
avoid competing listeners. Update preserved settings after changing environments.

## Verify and clean up

Check Connected consent, Enabled configs, and successful **source registration** in
[Connector Namespaces](https://connectors.azure.com/). An Enabled resource alone
does not prove source registration succeeded. Create, modify, and delete a test row
in the configured logical table, then check logs for `Received OnDataverseRowChanged trigger`.
For action-performed, execute the actual selected action; live delivery for this
optional scenario has not been verified.

Handlers do not log payload fields. Never commit tokens or private settings.
Before `azd down --purge`, complete the action source-cleanup checks above. Resource
group deletion alone does not prove that Dataverse source callbacks are gone.