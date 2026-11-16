# Microsoft Dataverse polling triggers (Python)

The Functions host receives Dataverse events from the Connector Namespace polling endpoint. All handlers use raw `str` bindings and log only the trigger name. No public callback is required.

| Function | Connector operation |
| --- | --- |
| `OnDataverseRowChanged` | [`SubscribeWebhookTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-a-row-is-added,-modified-or-deleted) |
| `OnDataverseActionPerformed` | [`BusinessEventsTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-an-action-is-performed) |
| `OnDataverseRowAdded` | `SubscribeOnNewItems` |
| `OnDataverseRowModified` | `SubscribeOnUpdatedItems` |
| `OnDataverseRowDeleted` | `SubscribeOnDeletedItems` |

This folder is a standalone app. Run all commands from this folder; no parent or sibling files are required.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- PowerShell 7.3+ on every platform, including when using the Bash wrapper.
- A Dataverse organization and an account permitted to authorize the connection and register organization-scoped event subscriptions.
- A supported Python version; the template deploys Python 3.14. The app preprovision hook also requires Python; set `PYTHON` to an interpreter path if needed. For local runs, install [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- `azure-functions>=2.4.0` for Python 3.13+ and `azurefunctions-extensions-connectors>=1.0.0`.

For Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before installing `requirements.txt`, which does not install the older SDK, and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; the template and local settings example include it.

## Deploy to Azure

```powershell
az login
azd auth login
azd env new dataverse-polling
azd env set DATAVERSE_ENVIRONMENT_URL https://contoso.crm.dynamics.com
azd up
```

Authorize with an account that can register Dataverse events. After consent, choose the separate-row table and scope, and the action catalog, category, table, and action from the connector's returned options. The hook saves those choices in the selected azd environment. It creates all five Poll configs as enabled before provisioning the Function App with the polling endpoint and deploying the code. Reruns preserve unrelated Function App settings while refreshing the sample-managed settings. The combined row trigger uses logical table `account` by default, `message=7`, and organization scope `4`.

The action trigger needs an available cataloged business event. If the connector returns no choices, configure an event and check the account's permissions before rerunning `azd up`.

## Optional configuration

| Setting | Purpose |
| --- | --- |
| `DATAVERSE_TABLE_NAME` | Logical table name for the combined trigger; defaults to `account`, not an entity-set name. |
| `DATAVERSE_ENTITY_SET_NAME` | Separate-row Table Name selector returned by `GetTables`. |
| `DATAVERSE_ROW_SCOPE` | Separate-row scope returned by `GetScopeFilters`; do not reuse combined-trigger `scope=4`. |
| `DATAVERSE_EVENT_CATALOG`, `DATAVERSE_EVENT_CATEGORY`, `DATAVERSE_EVENT_TABLE`, `DATAVERSE_EVENT_ACTION` | Exact action selector values returned by the connector. |
| `CONNECTOR_NAMESPACE_LOCATION`, `TELEMETRY_LOCATION` | Override the namespace or monitoring region. |

Set the selector values before `azd up` to use them without prompts. The combined logical table and separate-row table are selected independently; choose matching tables if all row triggers should monitor the same table. The hook validates existing operations, selectors, connection, destination, and delivery mode before changes; legacy or mismatched configs require explicit cleanup or a fresh environment.

### Action subscription cleanup

The hook maintains an ignored `.azure/dataverse-action-cleanup-*.json` journal bound to the exact action registration. Before replacing an action or deleting resources, inspect Dataverse for its exact owned `callbackregistration`, verify its selectors and destination, remove only that registration, and confirm GET returns 404. Only after confirming cleanup, archive the matching journal outside this app before creating a replacement. Preserve the journal and unrelated registrations on failure. The scripts do not automatically delete Dataverse callbacks; resource group deletion alone does not prove source cleanup.

## Local development

Start Azurite separately. After provisioning, run:

```powershell
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
az login
azd hooks run postdeploy
func start
```

The hook creates local settings if absent and preserves existing files. After changing selections, use `pwsh ./infra/scripts/postdeploy.ps1 -ForceLocalSettings` to replace them explicitly. Use developer credentials locally. Stop the deployed app or use separate configs to avoid competing listeners.

## Verify and clean up

Check Connected consent, enabled configs, and successful **source registration** in [Connector Namespaces](https://connectors.azure.com/). Create, modify, and delete a test row and check the corresponding row-trigger logs. Action delivery requires executing the selected action on an authorized test fixture.

Complete the action source-cleanup steps above before running `azd down --purge` from this folder. Never commit credentials or local settings.
