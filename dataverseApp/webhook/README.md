# Microsoft Dataverse webhook triggers (Python)

Connector Namespace sends Dataverse events to the Functions connector callback, authenticated with the `connector_extension` system key. All handlers use raw `str` bindings and log only the trigger name.

| Function | Connector operation |
| --- | --- |
| `OnDataverseRowChanged` | [`SubscribeWebhookTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-a-row-is-added,-modified-or-deleted) |
| `OnDataverseActionPerformed` | [`BusinessEventsTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-an-action-is-performed) |
| `OnDataverseRowAdded` | `SubscribeOnNewItems` |
| `OnDataverseRowModified` | `SubscribeOnUpdatedItems` |
| `OnDataverseRowDeleted` | `SubscribeOnDeletedItems` |

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- PowerShell 7.3+ on every platform, including when using the Bash wrapper.
- A Dataverse organization and an account permitted to authorize the connection and register organization-scoped event subscriptions.
- A supported Python version; the template deploys Python 3.14. For local runs, install [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0b1` for Python 3.13+ or `azure-functions>=1.27.0b1` for older supported versions, and `azurefunctions-extensions-connectors>=1.0.0b4`. The requirements file selects the SDK family.

For Python 3.12 and older, set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it. Install the version-specific packages from `requirements.txt`.

## Deploy to Azure

```powershell
az login
azd auth login
azd env new dataverse-webhook
azd env set DATAVERSE_ENVIRONMENT_URL https://contoso.crm.dynamics.com
azd up
```

Authorize with an account that can register Dataverse events. After consent, choose the separate-row table and scope, and the action catalog, category, table, and action from the connector's returned options. The hook saves those choices in the selected azd environment and registers all five webhook configs using the deployed app's hostname and connector extension system key. The combined row trigger uses logical table `account` by default, `message=7`, and organization scope `4`.

The action trigger needs an available cataloged business event. If the connector returns no choices, configure an event and check the account's permissions before rerunning `azd hooks run postdeploy`.

## Optional configuration

| Setting | Purpose |
| --- | --- |
| `DATAVERSE_TABLE_NAME` | Logical table name for the combined trigger; defaults to `account`, not an entity-set name. |
| `DATAVERSE_ENTITY_SET_NAME` | Separate-row Table Name selector returned by `GetTables`. |
| `DATAVERSE_ROW_SCOPE` | Separate-row scope returned by `GetScopeFilters`; do not reuse combined-trigger `scope=4`. |
| `DATAVERSE_EVENT_CATALOG`, `DATAVERSE_EVENT_CATEGORY`, `DATAVERSE_EVENT_TABLE`, `DATAVERSE_EVENT_ACTION` | Exact action selector values returned by the connector. |
| `CONNECTOR_NAMESPACE_LOCATION`, `TELEMETRY_LOCATION` | Override the namespace or monitoring region. |

Set the selector values before `azd up` to use them without prompts. The combined logical table and separate-row table are selected independently; choose matching tables if all row triggers should monitor the same table. The hook validates existing operations, selectors, connections, destinations, callbacks, and delivery modes before changes. Matching enabled configs are preserved; disabled, legacy, or mismatched row configs require explicit cleanup or a fresh environment.

### Action subscription cleanup

The hook maintains an ignored `.azure/dataverse-action-cleanup-*.json` journal bound to the exact action registration. Before replacing an action or deleting resources, inspect Dataverse for the exact owned `callbackregistration`, verify its selectors and destination, remove only that registration, and confirm GET returns 404. Only then archive the matching journal outside this app. Preserve unrelated registrations; the scripts do not automatically delete Dataverse callbacks.

## Local development

- Start Azurite separately.
- Use the generated local settings or copy `local.settings.example.json` to `local.settings.json` if absent:

```powershell
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

- To receive local events, expose the host through a secure public HTTPS tunnel and configure separate callbacks using the local function names and local `connector_extension` system key.
- Core Tools bypasses key checks by default; enable authentication before exposing the host.
- The hook targets Azure, not localhost; rerun it to restore deployed callbacks after manual changes.
- After changing selections, use `pwsh ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` to replace local settings explicitly.

## Verify and clean up

Check Connected consent, enabled configs, and successful **source registration** in [Connector Namespaces](https://connectors.azure.com/). Create, modify, and delete a test row and check the corresponding row-trigger logs. Action delivery requires executing the selected action on an authorized test fixture.

Complete the action source-cleanup steps above before running `azd down --purge` from this folder. Never commit callback keys, credentials, or local settings.
