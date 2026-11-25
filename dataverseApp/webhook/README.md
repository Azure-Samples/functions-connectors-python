<!--
---
name: "Azure Functions Connector Samples (Python): Microsoft Dataverse webhook"
description: Receive Microsoft Dataverse connector events through webhook delivery in a Python Azure Functions app deployed using azd.
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure
- azure-functions
urlFragment: functions-connectors-dataverse-webhook-python
---
-->

# Microsoft Dataverse webhook triggers (Python)

The Connector Namespace calls the deployed function's connector callback, authenticated with the `connector_extension` system key.

| Function | Connector operation |
| --- | --- |
| `OnDataverseRowChanged` | [`SubscribeWebhookTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-a-row-is-added,-modified-or-deleted) |
| `OnDataverseActionPerformed` | [`BusinessEventsTrigger`](https://learn.microsoft.com/connectors/commondataservice/#when-an-action-is-performed) |
| `OnDataverseRowAdded` | `SubscribeOnNewItems` |
| `OnDataverseRowModified` | `SubscribeOnUpdatedItems` |
| `OnDataverseRowDeleted` | `SubscribeOnDeletedItems` |

Handlers log only the trigger name, not event content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+ with the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- PowerShell 7.3+ (required by the deployment hooks on every platform).
- A Dataverse organization and an account that can authorize the connection and register organization-scoped event subscriptions.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app uses `azure-functions>=2.4.0` (Python 3.13+) and `azurefunctions-extensions-connectors>=1.0.0`; the template deploys Python 3.14. For older Python versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

Set your Dataverse organization URL (not its friendly name), then run `azd up`:

```bash
az login
azd auth login
azd env new dataverse-webhook
azd env set DATAVERSE_ENVIRONMENT_URL https://contoso.crm.dynamics.com
azd up
```

`azd up` asks you to:

1. Sign in to the Dataverse connection.
2. Choose the table and scope for the separate row triggers.
3. Choose the action trigger's catalog, category, table, and action. If no choices are returned, set up a cataloged business event and check your account's permissions, then rerun `azd up`.

All five triggers are configured. Your choices are reused by later `azd up` runs, which also deploy code changes. To retry after a failure, rerun `azd up`.

### Optional settings

Set these with `azd env set` before `azd up` to skip the matching prompts:

| Setting | Purpose |
| --- | --- |
| `DATAVERSE_TABLE_NAME` | Logical table name (such as `account`) for `OnDataverseRowChanged`; defaults to `account`. |
| `DATAVERSE_ENTITY_SET_NAME`, `DATAVERSE_ROW_SCOPE` | Table and scope for the separate row triggers, as returned by the connector's table and scope lists. |
| `DATAVERSE_EVENT_CATALOG`, `DATAVERSE_EVENT_CATEGORY`, `DATAVERSE_EVENT_TABLE`, `DATAVERSE_EVENT_ACTION` | Action trigger selectors, as returned by the connector. |
| `CONNECTOR_NAMESPACE_LOCATION`, `TELEMETRY_LOCATION` | Override the namespace or monitoring region. |

`OnDataverseRowChanged` and the separate row triggers select their tables independently; pick the same table if all row triggers should monitor it. Existing trigger configurations that are disabled or don't match your choices aren't changed; remove them or use a new azd environment.

## Local development

1. Start Azurite.
2. Create a virtual environment, install dependencies, and start the host with authentication enabled:

   ```bash
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   func start --enableAuth
   ```

`azd up` creates `local.settings.json` if it doesn't exist and leaves an existing file unchanged; you can also copy `local.settings.example.json`. To regenerate it after changing selections, run `pwsh ./infra/scripts/postdeploy.ps1 -ForceLocalSettings`.

Deployed callbacks point to Azure, not localhost. To receive events locally, expose the host through a secure HTTPS tunnel and configure separate callbacks that use the local function names and local `connector_extension` system key. Core Tools skips key checks unless started with `--enableAuth`.

## Test

1. In [Connector Namespaces](https://connectors.azure.com/), check that the connection is **Connected** and the triggers are enabled with successful source registration.
2. Create, modify, and delete a test row in the monitored table, then check the matching function logs.
3. To test the action trigger, run the selected action on an authorized test record.

## Deprovision

Deleting Azure resources doesn't remove the action trigger's Dataverse event registration. Before `azd down`, or before replacing the action trigger, remove that `callbackregistration` in Dataverse (verify its selectors and destination first, and leave unrelated registrations alone). Then archive the matching `.azure/dataverse-action-cleanup-*.json` file outside this folder.

```bash
azd down --purge
```

Never commit callback keys, credentials, or `local.settings.json`.
