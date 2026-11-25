<!--
---
name: "Azure Functions Connector Samples (Python): Salesforce polling"
description: Receive Salesforce connector events with polling in a Python Azure Functions app deployed using Azure Developer CLI (azd).
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure
- azure-functions
urlFragment: functions-connectors-salesforce-polling-python
---
-->

# Salesforce polling triggers (Python)

The Functions host pulls Salesforce record events from the Connector Namespace polling endpoint. No public endpoint is required.

| Function / connector operation | Binding |
| --- | --- |
| [`OnSalesforceNewItems`](https://learn.microsoft.com/connectors/salesforce/#when-a-record-is-created) | `List[salesforce.Item]` |
| [`OnSalesforceUpdatedItems`](https://learn.microsoft.com/connectors/salesforce/#when-a-record-is-modified) | `List[salesforce.Item]` |

Handlers log the function name and record count, not record content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python for the deployment hooks, with PowerShell 7 on Windows or `sh` on macOS/Linux.
- Contributor plus Role Based Access Control Administrator (or User Access Administrator) on the target subscription.
- A Salesforce **production** or **Developer Edition** org. Sandbox orgs are not supported when deploying with `azd`, because the connection signs in through `login.salesforce.com`.
- A Salesforce account with API access and read access to the selected objects, fields, and records.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- Python SDK: `requirements.txt` installs the right `azure-functions` version for your Python; see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```sh
az login
azd auth login
azd env new salesforce-polling
azd up
```

`azd up` asks you to:

1. Sign in to Salesforce.
2. **Configure** or **Skip** each trigger. For each configured trigger, pick the object from the live list; optional `$filter`, `$orderby`, and `$select` can be skipped. Configure at least one trigger.

Skipped functions are still deployed with their listeners disabled.

Choices are saved in the azd environment and reused by later `azd up` runs. To choose again, run `azd env set POLLING_TRIGGER_INPUTS ""`, then `azd up`.

To skip prompts, copy [trigger-inputs.example.json](trigger-inputs.example.json) to `trigger-inputs.json` (an array of `{ "functionName", "operationName", "parameters": [{ "name", "value" }] }`), keep only the triggers to configure, and replace each placeholder with an object API name such as `Account`. It takes precedence over saved choices.

`azd up` also deploys later code changes. To retry after a failure, rerun `azd up`.

| Optional setting | Purpose |
| --- | --- |
| `CONNECTOR_NAMESPACE_LOCATION` | Connector Namespace region (default `brazilsouth`). |
| `APPLICATION_INSIGHTS_LOCATION` | Application Insights region, if different from the app. |

## Local development

1. Start Azurite.
2. Create and activate a virtual environment, then install dependencies:

   ```sh
   python -m venv .venv
   . .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Stay signed in with `az login` as the deploying user, then run `func start`.

`azd up` creates `local.settings.json` if absent. To regenerate it, run `sh ./infra/scripts/postdeploy.sh --force` (or `./infra/scripts/postdeploy.ps1 -ForceLocalSettings`). Stop the deployed app while testing locally; both hosts would compete for the same events.

## Test

Create and then edit a record of a configured object in Salesforce. Confirm invocations and record counts in the function logs, and the trigger configs in [Connector Namespaces](https://connectors.azure.com/).

## Deprovision

```sh
azd down --purge
```

Never commit `local.settings.json` or `trigger-inputs.json`.
