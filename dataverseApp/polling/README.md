# Microsoft Dataverse polling triggers (Python)

The Functions host pulls Dataverse events from the Connector Namespace, so the app needs no public endpoint.

| Function | Connector operation |
| --- | --- |
| `OnDataverseRowChanged` | [`SubscribeWebhookTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-a-row-is-added,-modified-or-deleted) |
| `OnDataverseActionPerformed` | [`BusinessEventsTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-an-action-is-performed) |
| `OnDataverseRowAdded` | `SubscribeOnNewItems` |
| `OnDataverseRowModified` | `SubscribeOnUpdatedItems` |
| `OnDataverseRowDeleted` | `SubscribeOnDeletedItems` |

Handlers log only the trigger name, not event content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+ with the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python and PowerShell 7.3+ (required by the deployment hooks on every platform).
- A Dataverse organization and an account that can authorize the connection and register organization-scoped event subscriptions.
- For local runs: [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app uses `azure-functions>=2.4.0` (Python 3.13+) and `azurefunctions-extensions-connectors>=1.0.0`; the template deploys Python 3.14. For older Python versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

Set your Dataverse organization URL (not its friendly name), then run `azd up`:

```bash
az login
azd auth login
azd env new dataverse-polling
azd env set DATAVERSE_ENVIRONMENT_URL https://contoso.crm.dynamics.com
azd up
```

`azd up` asks you to:

1. Sign in to the Dataverse connection.
2. Choose **Configure** or **Skip** for each trigger. Configure at least one. Configure the action trigger only if a cataloged business event exists and your account has the required permissions.
3. For each configured trigger, pick inputs such as table and scope from the connector's lists, or type them where no list exists. Optional filters can be skipped.

Skipped functions are still deployed with their listeners disabled.

Your choices are reused by later `azd up` runs, which also deploy code changes. To choose again, run `azd env set POLLING_TRIGGER_INPUTS ""`, then `azd up`. To retry after a failure, rerun `azd up`.

To skip the prompts, create `trigger-inputs.json` in this folder: an array of `{ "functionName", "operationName", "parameters": [{ "name", "value" }] }` objects using connector parameter names. It takes precedence over saved choices.

### Optional settings

Set these with `azd env set` before `azd up` to prefill trigger inputs:

| Setting | Purpose |
| --- | --- |
| `DATAVERSE_TABLE_NAME` | Logical table name (such as `account`) for `OnDataverseRowChanged`; defaults to `account`. |
| `DATAVERSE_ENTITY_SET_NAME`, `DATAVERSE_ROW_SCOPE` | Table and scope for the separate row triggers, as returned by the connector's table and scope lists. |
| `DATAVERSE_EVENT_CATALOG`, `DATAVERSE_EVENT_CATEGORY`, `DATAVERSE_EVENT_TABLE`, `DATAVERSE_EVENT_ACTION` | Action trigger selectors, as returned by the connector. |
| `CONNECTOR_NAMESPACE_LOCATION`, `TELEMETRY_LOCATION` | Override the namespace or monitoring region. |

The separate row triggers overlap `OnDataverseRowChanged` when they monitor the same table.

## Local development

1. Start Azurite.
2. Create a virtual environment, install dependencies, and start the host:

   ```bash
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   az login
   func start
   ```

`azd up` creates `local.settings.json` if it doesn't exist and leaves an existing file unchanged. To regenerate it after changing trigger choices, run `sh ./infra/scripts/configure-triggers.sh finish --force-local-settings` (or `./infra/scripts/configure-triggers.ps1 finish --force-local-settings` in PowerShell). Stop the deployed app while running locally to avoid competing listeners.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), check that the connection is **Connected** and the configured triggers are enabled with successful source registration.
2. Create, modify, and delete a test row in the monitored table, then check the matching function logs.
3. To test the action trigger, run the selected action on an authorized test record.

## Deprovision

Deleting Azure resources doesn't remove the action trigger's Dataverse event registration. Before `azd down`, or before replacing the action trigger, remove that `callbackregistration` in Dataverse (verify its selectors and destination first, and leave unrelated registrations alone). Then archive the matching `.azure/dataverse-action-cleanup-*.json` file outside this folder.

```bash
azd down --purge
```

Never commit credentials or `local.settings.json`.
