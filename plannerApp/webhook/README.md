# Planner webhook events

This folder is an independently copyable Function App. Its code, infrastructure, hooks, setup helper and ignore rules are all local. Run commands from this folder. All three rich bindings use `typing.List[GetTaskResponseV2]`; handlers log only the function name and item count, never task data.

| Function | Connector operation | Required wire selectors |
| --- | --- | --- |
| `OnPlannerCompleteTask` | `OnCompleteTask_V3` | `groupId`, `id` |
| `OnPlannerNewTask` | `OnNewTask_V3` | `groupId`, `id` |
| `OnPlannerTaskAssignedToMe` | `OnTaskAssignedToMe_V2` | None; uses the consenting user |

`id` is the **plan ID**, not a task ID. Group and plan IDs must identify resources the consenting Microsoft 365 user can access. The Group Id selector maps to `ListGroups`; Plan Id maps to `ListGroupPlans` with that group. This sample does not run dynamic pickers or discover plans automatically. Obtain actual IDs from your Planner/Microsoft 365 resources or those connector operations, not display names. Assigned-to-me needs no IDs.

## Prerequisites and permissions

- Azure Developer CLI, Azure CLI with the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli) supporting `connection authenticate`, and PowerShell 7 or a POSIX shell. Hooks use Python (`python` on Windows, `python3` on POSIX) and the standard library only.
- An Azure subscription and permission to create a resource group, Flex Consumption Function App, storage, monitoring, Connector Namespace and connection. The templates assign Azure roles: use Owner, or Contributor plus Role Based Access Control Administrator at a scope covering those assignments. Register the required `Microsoft.Web`, `Microsoft.Storage`, `Microsoft.Insights` and `Microsoft.OperationalInsights` providers if your subscription has not registered them; provider registration needs subscription permission.
- A Microsoft 365 account with Planner access and permission to read the chosen group/plan and tasks. Sign in to OAuth as the user to monitor. Azure RBAC does not grant Planner data access. Your tenant's consent policy may require an administrator to approve connector permissions. Do not substitute application credentials for this delegated OAuth connection.
- A supported local Python runtime. Deployment uses Python **3.14**. [requirements.txt](requirements.txt) installs `azure-functions>=1.27.0b1` on Python below 3.13, `azure-functions>=2.4.0` on Python 3.13+, and `azurefunctions-extensions-connectors>=1.0.0`. The extension supplies its connector SDK dependency; do not install a separate direct `azure-connectors` requirement.
- For local execution only: Functions Core Tools v4 with connector support and Azurite. [host.json](host.json) uses the stable `Microsoft.Azure.Functions.ExtensionBundle` ID with `[4.41.2, 5.0.0)`. Set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; generated settings and the checked-in example include it.

Provisioning grants the signed-in developer a connection access policy and storage data roles. The app gets its own connection policy, Blob Data Owner, Queue Data Contributor, Table Data Contributor and Monitoring Metrics Publisher roles through its system-assigned identity. No redundant namespace-self connection policy, FIC or client secret is needed. Use a user identity for the deployer parameter, not a service principal. The setup identity also needs permission to list the Function App's system keys and update/read its app settings.

## Build and deploy

Create a virtual environment with `python -m venv .venv`, activate it (`.venv\Scripts\Activate.ps1` on PowerShell or `. .venv/bin/activate` on POSIX), then run `python -m pip install -r requirements.txt`. No separate pre-install of the Functions SDK is required for older runtimes.

Run `az login`, `az account set --subscription <subscription-id>`, `azd auth login`, and `azd env new <unique-environment-name>`. Set `azd env set AZURE_SUBSCRIPTION_ID <subscription-id>` and `azd env set AZURE_LOCATION <supported-region>`. Optionally set `CONNECTOR_NAMESPACE_LOCATION` (default `westcentralus`) and `APPLICATION_INSIGHTS_LOCATION` with `azd env set`. Use a separate environment and resource group from the polling sample. Do not override app identity outputs with names from another app.

Copy [trigger-inputs.example.json](trigger-inputs.example.json) to ignored trigger-inputs.json, replace placeholders with actual Group Id and Plan Id, and remove unselected objects. The `id` key means plan ID, not task ID. Assigned-to-me uses the consenting user and requires an empty parameter array. Each entry must use the exact reviewed function/operation pair and parameter keys. Empty selections, duplicates, unknown keys and placeholders fail before source writes.

If no file exists, the hook prompts configure/skip for each event and asks for real IDs. `PLANNER_GROUP_ID` and `PLANNER_PLAN_ID` can supply those IDs, and `PLANNER_TRIGGER_INPUTS` can supply the complete JSON array. File input wins over the environment array. This sample does not automate dynamic pickers. Select at least one event.

Run `azd up` here. The preprovision hook inventories the intended app without reading its settings and fails closed on inventory errors or ambiguity. On reprovision, ARM reads the existing app settings and [app-settings.bicep](infra/app-settings.bicep) merges sample overrides; unrelated settings survive. All sample listeners start disabled. After deploying code, the interactive hook completes OAuth if needed, verifies `Connected`, and obtains the **connector_extension system key**, not a host/function key. Keep the normal terminal open for visible CLI prompts and complete browser consent; do not redirect or publish that transcript. The helper captures noninteractive key/settings commands. It uses the actual deployed hostname for `/runtime/webhooks/connector?functionName=...`. The callback key stays in `notificationDetails.authentication` with `type=QueryString`, `name=code`; the helper never prints it or adds it to the callback URL.

Webhook decorators use the default delivery mode, with no Poll-only fields. Config names use the connection-specific webhook prefix. Before any source/settings write, the hook preflights every existing same-name resource's ID, function, operation, connection, delivery mode and ownership metadata. Foreign resources stop setup. The helper disables listeners, registers selected sources, waits for successful provisioning, disables deselected owned sources without deleting them, and enables only selected listeners after successful source/settings verification. Bicep creates no trigger configs. Reruns preserve consent and reuse unchanged resources. Updates preserve writable metadata, recurrence and other properties while stripping read-only fields. ARM pagination is bounded to the same collection; every Azure CLI call pins the subscription. A failed multi-resource run may leave registered sources with listeners disabled; fix the cause and retry.

Retry with `azd hooks run postdeploy` here. [postdeploy.ps1](infra/scripts/postdeploy.ps1) accepts `-InputsFile` and `-Force`; [postdeploy.sh](infra/scripts/postdeploy.sh) accepts `--inputs` and `--force`. To retain another input file for `azd up` or hook reruns, set `azd env set PLANNER_INPUTS_FILE <absolute-file-path>`. Explicit file input takes precedence over the default file and JSON environment input. Both wrappers use only this mode's [setup helper](infra/scripts/setup.py).

## Local run and live checks

The hook writes private ignored local settings for Azurite and the Python worker, including `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, and preserves an existing file byte-for-byte by default. You can also start from the [disabled local settings example](local.settings.example.json). Start Azurite and run `func start` in the activated environment to index the typed handlers.

Request/settings JSON and callback authentication use private temporary files restricted to the current user, with cleanup on success and failure. Local writes are atomic and reject links/junctions/directories. The mode-local [.gitignore](.gitignore) excludes real settings, source inputs, azd state and staging directories even when this folder is copied alone. Never commit keys, real source IDs, settings or OAuth transcripts. Noninteractive CLI output is captured and errors omit sensitive details.

Running locally does **not** register or retarget live callbacks. The automated hook always targets the deployed app's actual hostname and key. Live local webhook testing needs a reachable HTTPS origin, the local connector extension system key, and a separately owned subscription created through Connector Namespaces with `uriQuery`/QueryString authentication. Keep the key in authentication metadata, never logs or source control. Do not retarget the deployed sample's source or use a cloud extension key for a local host. This sample does not automate local tunnels or local callback registration.

Check the connection is `Connected`, selected sources are `Enabled`, and deselected owned sources/listeners are `Disabled`. Create, complete or assign a task as appropriate; inspect trigger-name/count logs. Check source registration and connection permissions if no event arrives. A failed or partial hook run keeps listeners disabled; fix the cause and retry.

When finished, run `azd down --purge` from this mode's environment after confirming it contains no resources you need to keep.

**No live deployment, host startup, OAuth or event delivery was verified.** Offline validation does not prove those behaviors.