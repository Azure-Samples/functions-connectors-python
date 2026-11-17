# Planner event samples (Python)

[Polling](polling/README.md) and [webhook](webhook/README.md) are independently copyable Function App projects. Each includes its own infrastructure, setup helper, platform hooks, ignore rules and full permission/setup guidance. Each covers three events with the same function names and `typing.List[GetTaskResponseV2]` rich bindings. Logs contain only the trigger name and item count, never task content.

| Function | Connector operation | Required wire selectors |
| --- | --- | --- |
| `OnPlannerCompleteTask` | `OnCompleteTask_V3` | `groupId`, `id` |
| `OnPlannerNewTask` | `OnNewTask_V3` | `groupId`, `id` |
| `OnPlannerTaskAssignedToMe` | `OnTaskAssignedToMe_V2` | None; uses the connected user |

`id` means **plan ID**, not task ID. Group and plan IDs must belong to resources the consenting Microsoft 365 account can access. The completed/new-task operations use GET routes under `/v2/v1.0/planner/.../plans/{id}/tasks`; assigned-to-me uses `/v1.0/me/planner/ontaskassignedtome_trigger/tasks`.

## Reviewed source contract

The operation names, required keys and function names match the Node Planner webhook reference at commit `158d7e9944caa99f12ec481f1a837320720916d6`, its operation-request resolver and README, and Python `azure.connectors.planner.TRIGGER_OPERATIONS`. The SDK trigger metadata is not a callable client-method surface. The extension's `GetTaskResponseV2` wrapper delegates list deserialization to the generated Planner SDK task model.

Swagger declares a Group Id dynamic selector through `ListGroups`. Plan Id uses `ListGroupPlans` with the selected `groupId`. These samples **do not implement automated pickers**. Supply real IDs in the mode's ignored trigger-input file or enter them at the prompts. The assigned-to-me trigger needs neither ID. Only the reviewed required keys are accepted; optional or guessed wire parameters are rejected.

## Python dependencies

Both projects require `azurefunctions-extensions-connectors>=1.0.0`; its dependency supplies the connector SDK. No direct `azure-connectors` requirement is needed. Requirements install `azure-functions>=1.27.0b1` for `python_version < '3.13'` and `azure-functions>=2.4.0` for `python_version >= '3.13'`. No manual Functions SDK pre-install is needed. The deployed apps use Python 3.14; local development can use older supported runtimes. Generated/example local settings set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`.

Both hosts use the stable `Microsoft.Azure.Functions.ExtensionBundle` ID and `[4.41.2, 5.0.0)`.

## Setup and safety

Each project uses its own mode-local helper: [polling setup](polling/infra/scripts/setup.py) or [webhook setup](webhook/infra/scripts/setup.py). Neither depends on parent or sibling files. Use a distinct azd environment for each mode. Do not point both environments at the same resource group. The templates create Python 3.14 Flex Consumption (`FC1`) apps with no always-ready instances, system-assigned identity, AVM storage and monitoring, Entra-only monitoring ingestion, and function/developer connection policies. There is no redundant namespace-self policy. Blob, queue and table host-storage access uses managed identity. Function roles are assigned after the app exists. No FIC, client credentials or cloud `FUNCTIONS_WORKER_RUNTIME` setting is used.

Bicep creates infrastructure, **not trigger configs**. Polling uses azd 1.33+ layers: foundation -> consent and validated selection -> enabled Poll configs with verified endpoint/listener outputs -> Function App infrastructure -> code deployment. Its postdeploy hook only generates local settings. Webhook provisioning disables sample listeners; its postdeploy hook gets the deployed extension system key and registers callbacks. Both source setup paths validate inputs, preserve existing OAuth consent or invoke `connection authenticate --timeout 300 --no-access-policy`, and require `Connected` before source/settings writes. Authentication inherits the normal terminal: keep it open, complete the browser flow, and answer visible prompts. Do not redirect, capture or publish the OAuth transcript. A timeout is a failure, not authorization.

The hook checks every existing same-name resource's metadata, ID, operation, connection and mode before changing any source. Names use the connection prefix plus mode and function name. Foreign sources stop setup. Trigger pagination follows only bounded, non-repeated URLs in the same ARM collection. Every Azure CLI command pins the subscription from the selected azd environment.

Before registration the helper disables and verifies listeners if an app already exists. It creates selected sources, waits for successful provisioning, disables deselected **owned** sources by changing only state, and never deletes sources. Reruns reuse unchanged configs; updates preserve writable metadata, recurrence and other properties while stripping read-only fields. Polling passes verified settings to the app layer; webhook applies and verifies them after registration. Both app templates read existing settings and merge sample overrides, preserving unrelated values on reprovision. This is not an atomic multi-resource transaction: a failed run can leave registered sources with disabled listeners; rerun after fixing the cause.

Settings and callback keys go through private JSON files, with current-user Windows ACLs or POSIX permissions and cleanup on every exit. Noninteractive command output is captured; helper errors never include keys, source IDs, app settings or callback authentication. Interactive OAuth output belongs to the CLI and remains visible in the terminal. A new local settings file is private and atomic. Existing bytes remain unchanged unless the hook receives `--force` (PowerShell `-Force`). Never commit real local settings or trigger inputs. The checked-in examples contain no secrets and placeholder IDs are deliberately rejected.

## Validation limits

Offline validation can check the Python handlers and actual helper using mock CLI responses, Bicep compilation, PowerShell/Bash syntax, and the official azd YAML schema. It does not prove cloud support, OAuth permissions, host startup with disabled listeners, source registration or live event delivery. **No live deployment or event delivery was verified for these samples.** Connector Gateway preview resource types may produce Bicep `BCP081` warnings because the compiler lacks their schemas.