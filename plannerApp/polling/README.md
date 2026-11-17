# Planner polling events

This folder is an independently copyable Function App. Its code, infrastructure, hooks, setup helper and ignore rules are all local. Run commands from this folder. All three rich bindings use `typing.List[GetTaskResponseV2]`; handlers log only the function name and item count, never task data.

| Function | Connector operation | Required wire selectors |
| --- | --- | --- |
| `OnPlannerCompleteTask` | `OnCompleteTask_V3` | `groupId`, `id` |
| `OnPlannerNewTask` | `OnNewTask_V3` | `groupId`, `id` |
| `OnPlannerTaskAssignedToMe` | `OnTaskAssignedToMe_V2` | None; uses the consenting user |

`id` is the **plan ID**, not a task ID. Group and plan IDs must identify resources the consenting Microsoft 365 user can access. The Group Id selector maps to `ListGroups`; Plan Id maps to `ListGroupPlans` with that group. This sample does not run dynamic pickers or discover plans automatically. Obtain actual IDs from your Planner/Microsoft 365 resources or those connector operations, not display names. Assigned-to-me needs no IDs.

## Prerequisites and permissions

- Azure Developer CLI **1.33+** for infrastructure layers, Azure CLI with the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli) supporting `connection authenticate`, and PowerShell 7 or a POSIX shell. Hooks use Python (`python` on Windows, `python3` on POSIX) and the standard library only.
- An Azure subscription and permission to create a resource group, Flex Consumption Function App, storage, monitoring, Connector Namespace and connection. The templates assign Azure roles: use Owner, or Contributor plus Role Based Access Control Administrator at a scope covering those assignments. Register the required `Microsoft.Web`, `Microsoft.Storage`, `Microsoft.Insights` and `Microsoft.OperationalInsights` providers if your subscription has not registered them; provider registration needs subscription permission.
- A Microsoft 365 account with Planner access and permission to read the chosen group/plan and tasks. Sign in to OAuth as the user to monitor. Azure RBAC does not grant Planner data access. Your tenant's consent policy may require an administrator to approve connector permissions. Do not substitute application credentials for this delegated OAuth connection.
- A supported local Python runtime. Deployment uses Python **3.14**. [requirements.txt](requirements.txt) installs `azure-functions>=1.27.0b1` on Python below 3.13, `azure-functions>=2.4.0` on Python 3.13+, and `azurefunctions-extensions-connectors>=1.0.0`. The extension supplies its connector SDK dependency; do not install a separate direct `azure-connectors` requirement.
- For local execution only: Functions Core Tools v4 with connector support and Azurite. [host.json](host.json) uses the stable `Microsoft.Azure.Functions.ExtensionBundle` ID with `[4.41.2, 5.0.0)`. Set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`; both generated settings and the checked-in example include it.

Provisioning grants the signed-in developer a connection access policy and storage data roles. The app gets its own connection policy, Blob Data Owner, Queue Data Contributor, Table Data Contributor and Monitoring Metrics Publisher roles through its system-assigned identity. No redundant namespace-self connection policy, FIC or client secret is needed. Use a user identity for the deployer parameter, not a service principal.

## Build and deploy

Create a virtual environment with `python -m venv .venv`, activate it (`.venv\Scripts\Activate.ps1` on PowerShell or `. .venv/bin/activate` on POSIX), then run `python -m pip install -r requirements.txt`. No separate pre-install of the Functions SDK is required for older runtimes.

Run `az login`, `az account set --subscription <subscription-id>`, `azd auth login`, and `azd env new <unique-environment-name>`. Set `azd env set AZURE_SUBSCRIPTION_ID <subscription-id>` and `azd env set AZURE_LOCATION <supported-region>`. Optionally set `CONNECTOR_NAMESPACE_LOCATION` (default `westcentralus`) and `APPLICATION_INSIGHTS_LOCATION` with `azd env set`. Use a separate environment and resource group from the webhook sample. Do not override app identity outputs with names from another app.

Copy [trigger-inputs.example.json](trigger-inputs.example.json) to ignored trigger-inputs.json, replace every selected placeholder with an actual Group Id and Plan Id, and remove objects for unselected events. Do not change the reviewed function/operation pairs. Assigned-to-me may be the only selected entry and uses an empty parameter array. Empty arrays, duplicate events, unknown operations, wrong keys and placeholder values fail before source writes.

Alternatively, leave the file absent and answer configure/skip prompts. Enter real IDs when asked, or supply `PLANNER_GROUP_ID` and `PLANNER_PLAN_ID` in the source environment. `PLANNER_TRIGGER_INPUTS` can hold the complete reviewed JSON array. File input takes precedence over that environment variable. No interactive dynamic picker runs. At least one event must remain selected.

Run `azd up` here. Its workflow packages code, then performs these steps in order:

1. `azd provision base` creates foundation resources and the Planner connection, but **not** the Function App or trigger configs.
2. `azd provision triggers` runs the local interactive [setup helper](infra/scripts/setup.py). It validates source selection, preserves existing consent or invokes `connection authenticate --timeout 300 --no-access-policy`, and requires `Connected` before any source/settings writes. Keep the normal terminal open for visible CLI prompts and complete browser consent. Never redirect or publish that transcript. Failed or timed-out consent stops the layer.
3. After preflighting ownership of **all** existing same-name configs, the helper disables listeners on an existing app, creates selected **Enabled Poll** configs, disables deselected owned configs and waits for successful registration. It reads the real receive URI for each selected source. All must use HTTPS, the expected trigger/gateway path and the same gateway; there is no fabricated fallback endpoint. The layer publishes `connectorPollingEndpoint` and base64-encoded `triggerConfigSettingsEncoded` listener settings for the next layer.
4. `azd provision app` checks whether the app exists, reads its existing app settings in ARM, and merges sample overrides through [app-settings.bicep](infra/app-settings.bicep). It preserves unrelated settings while applying the verified endpoint, config names and selected/disabled listeners, then grants the app's managed identity access.
5. `azd deploy --all` deploys code. The local-only postdeploy hook writes local settings; it does not register or re-enable cloud sources.

The hook sets `ConnectorNamespace__pollingEndpoint` and all three `FunctionTriggerConfigName` values, then enables only selected functions. The decorator uses `connection="ConnectorNamespace"`, `DeliveryMode.POLL` and `%FunctionTriggerConfigName%`. No webhook key or callback is used.

To retry source setup or change selection, rerun `azd up`, or run `azd provision triggers`, `azd provision app`, then `azd deploy --all` in that order. To use another input file during these commands, set `azd env set PLANNER_INPUTS_FILE <absolute-file-path>` first. Explicit file input takes precedence over the default file and JSON environment input. For direct source setup, [prepare-sources.ps1](infra/scripts/prepare-sources.ps1) accepts `-InputsFile`, and [prepare-sources.sh](infra/scripts/prepare-sources.sh) accepts `--inputs`; subsequent layer commands must use the same file setting. Reruns preserve consent, reuse unchanged sources and disable deselected owned sources without deleting them.

Config names include the connection, mode and function. Existing IDs, operations, connections, delivery mode and ownership metadata must all match; foreign resources stop setup before changes. Updates preserve writable metadata and recurrence and strip read-only fields. Continuations stay in the same ARM collection and have loop/page limits. Every Azure CLI call pins the subscription. Partial registration is not atomic: a failed run may leave configs registered, with old app listeners disabled. Fix the cause and rerun the source/app layers; do not bypass their order.

`azd hooks run postdeploy` only regenerates missing local settings from verified layer outputs. [postdeploy.ps1](infra/scripts/postdeploy.ps1) accepts `-Force`, and [postdeploy.sh](infra/scripts/postdeploy.sh) accepts `--force`, to replace existing local settings explicitly. Source selection belongs to the triggers layer, not this hook.

## Local run and live checks

The hook creates ignored local settings with Azurite storage, `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, developer authentication and the service's real polling endpoint. Existing local settings remain byte-for-byte unchanged by default. The [local settings example](local.settings.example.json) starts all listeners disabled and is only a bootstrap example, not a configured Poll app. After consent and source creation, use the hook-generated settings, or explicitly force regeneration. Cloud storage/connection access uses managed identity; local runs use your Azure login, not a copied cloud credential setting.

Request/settings JSON uses private temporary files, restricted to the current user, with cleanup on failure as well as success. Local writes are atomic and reject links/junctions/directories. The mode-local [.gitignore](.gitignore) excludes real settings, source inputs, azd state and staging directories even when this folder is copied alone. Never commit secrets, real source IDs or OAuth transcripts. Noninteractive CLI output is captured and errors omit sensitive details.

Start Azurite and run `func start` in the activated environment. Local polling uses the deployer's Azure login and connection policy. A single Poll source is a queue consumer: stop the deployed listeners before local testing, or use a separate environment/connection and its generated settings. Do not assume cloud and local consumers each receive a copy. The helper does not stop the cloud app for you.

Check the connection is `Connected`, selected configs are `Enabled`, and unselected owned configs/listeners are `Disabled`. Create a task, complete a task, or assign a task to the consenting user, then inspect name/count logs. No source IDs or task content should appear. If setup fails, leave listeners disabled, fix consent, permissions, region or input issues, and rerun the triggers/app layers in order.

When finished, run `azd down --purge` from this mode's environment after confirming it contains no resources you need to keep.

**No live deployment, host startup or event delivery was verified.** Offline compilation and mock execution do not establish those results.