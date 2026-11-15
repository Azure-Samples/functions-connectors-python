# Microsoft Dataverse webhook triggers (Python)

Connector Namespace sends Dataverse events to the Functions connector callback, authenticated with the `connector_extension` system key. All handlers use raw `str` bindings and log only the trigger name.

| Function | Connector operation | Selection |
| --- | --- | --- |
| `OnDataverseRowChanged` | [`SubscribeWebhookTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-a-row-is-added,-modified-or-deleted) | Default |
| `OnDataverseActionPerformed` | [`BusinessEventsTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-an-action-is-performed) | Opt-in |
| `OnDataverseRowAdded` | `SubscribeOnNewItems` | Opt-in |
| `OnDataverseRowModified` | `SubscribeOnUpdatedItems` | Opt-in |
| `OnDataverseRowDeleted` | `SubscribeOnDeletedItems` | Opt-in |

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

Authorize with an account that can register Dataverse events. The hook registers selected webhook configs using the deployed app's actual hostname and connector extension system key. The default combined row trigger uses logical table `account`, `message=7`, and organization scope `4`.

## Optional configuration

| Setting | Purpose |
| --- | --- |
| `DATAVERSE_TABLE_NAME` | Logical table name for the combined trigger; defaults to `account`, not an entity-set name. |
| `DATAVERSE_ENABLE_ACTION_TRIGGER` | Set `true` to enable the action event; also set `DATAVERSE_EVENT_CATALOG`, `DATAVERSE_EVENT_CATEGORY`, `DATAVERSE_EVENT_TABLE`, and `DATAVERSE_EVENT_ACTION` to actual selector values. |
| `DATAVERSE_ENABLE_SEPARATE_ROW_TRIGGERS` | Set `true` to enable added, modified, and deleted operations. |
| `DATAVERSE_ENTITY_SET_NAME` | For separate rows, the Table Name selector returned by `GetTables`. |
| `DATAVERSE_ROW_SCOPE` | For separate rows, the exact selector returned by `GetScopeFilters` for that dataset/table; do not reuse combined-trigger `scope=4`. |
| `CONNECTOR_NAMESPACE_LOCATION`, `TELEMETRY_LOCATION` | Override the namespace or monitoring region. |

Optional action and separate-row triggers default to disabled. Separate row events overlap the combined trigger. The hook validates existing operations, selectors, connections, destinations, callbacks, and delivery modes before changes. Matching enabled configs are preserved; disabled, legacy, or mismatched row configs require explicit cleanup or a fresh environment. Turning off separate rows removes only matching owned namespace configs.

### Action subscription cleanup

The hook maintains an ignored `.azure/dataverse-action-cleanup-*.json` journal bound to the exact action registration. Disabling an action removes only the owned namespace config and fails until source cleanup is verified. Inspect Dataverse for the exact owned `callbackregistration`, verify its selectors and destination, remove only that registration, and confirm GET returns 404. Only then archive the matching journal outside this app and rerun. Preserve unrelated registrations; the scripts do not automatically delete Dataverse callbacks.

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

Check Connected consent, enabled configs, and successful **source registration** in [Connector Namespaces](https://connectors.azure.com/). Create, modify, and delete a test row and check the `OnDataverseRowChanged` log. Optional action delivery requires executing the selected action and has not been live-verified.

Complete the action source-cleanup steps above before running `azd down --purge` from this folder. Never commit callback keys, credentials, or local settings.
