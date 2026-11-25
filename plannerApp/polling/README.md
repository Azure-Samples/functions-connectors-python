<!--
---
name: "Azure Functions Connector Samples (Python): Planner polling"
description: Receive Microsoft Planner connector events with polling in a Python Azure Functions app deployed using Azure Developer CLI (azd).
page_type: sample
languages:
- python
- bicep
- azdeveloper
products:
- azure
- azure-functions
urlFragment: functions-connectors-planner-polling-python
---
-->

# Planner polling triggers (Python)

The Functions host pulls Planner events from the Connector Namespace polling endpoint. No public endpoint is required.

| Function / connector operation | Binding |
| --- | --- |
| `OnPlannerCompleteTask` / [`OnCompleteTask_V3`](https://learn.microsoft.com/connectors/planner/#when-a-task-is-completed) | `List[GetTaskResponseV2]` |
| `OnPlannerNewTask` / [`OnNewTask_V3`](https://learn.microsoft.com/connectors/planner/#when-a-new-task-is-created) | `List[GetTaskResponseV2]` |
| `OnPlannerTaskAssignedToMe` / [`OnTaskAssignedToMe_V2`](https://learn.microsoft.com/connectors/planner/#when-a-task-is-assigned-to-me) | `List[GetTaskResponseV2]` |

Handlers log the function name and item count, not task content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.33+, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python for the deployment hooks, plus PowerShell 7 on Windows.
- Azure permission to create resources and role assignments, such as Owner, or Contributor plus Role Based Access Control Administrator.
- A Microsoft 365 account with access to the Planner groups and plans to monitor. Your tenant's consent policy may require an administrator to approve the connector.
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app deploys on Python 3.14 and uses `azurefunctions-extensions-connectors>=1.0.0`. For older Python versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new planner-polling
azd up
```

`azd up` then asks you to:

1. Sign in to the Planner connection in the browser, if it isn't already connected.
2. Choose **Configure** or **Skip** for each trigger. Configure at least one.
3. For the completed and new task triggers, pick the group and plan from live lists. The assigned-to-me trigger needs no inputs.

Skipped functions are still deployed, with their listeners disabled.

Choices are saved in the azd environment and reused by later `azd up` runs. To choose again, run `azd env set POLLING_TRIGGER_INPUTS ""`, then `azd up`.

To skip prompts, copy [trigger-inputs.example.json](trigger-inputs.example.json) to `trigger-inputs.json` (ignored by git), keep only the triggers to configure, and replace the placeholders with real IDs. Each entry is `{ "functionName", "operationName", "parameters": [{ "name", "value" }] }`; `id` is the plan ID, not a task ID. The file takes precedence over saved choices.

`azd up` also deploys later code changes. To retry after a failure, rerun `azd up`.

| Optional setting | Purpose |
| --- | --- |
| `PLANNER_GROUP_ID`, `PLANNER_PLAN_ID` | Group and plan IDs to use instead of picking them. |
| `CONNECTOR_NAMESPACE_LOCATION` | Connector Namespace region (default `westcentralus`). |

## Local development

1. Start Azurite.
2. Install dependencies:

   ```bash
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   ```

3. Sign in with `az login`, then run `func start`.

`azd up` creates `local.settings.json` if it doesn't exist. To regenerate it, run `sh ./infra/scripts/postdeploy.sh --force` (or `./infra/scripts/postdeploy.ps1 -Force`).

Local and deployed listeners compete for the same events; stop the deployed app while testing locally.

## Test

Create a task, complete a task, or assign a task to yourself in a configured plan. Confirm the trigger configurations are enabled in [Connector Namespaces](https://connectors.azure.com/) and check the function logs for the function name and count.

## Deprovision

```bash
azd down --purge
```

Never commit credentials, local settings, or `trigger-inputs.json`.
