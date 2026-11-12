# Planner event samples (Python)

[Polling](polling/README.md) and [webhook](webhook/README.md) are separate Function App projects. Each covers three events with the same function names and typed `list[GetTaskResponseV2]` handlers. Logs contain only the trigger name and item count, never task content.

| Function | Connector operation | Required wire selectors |
| --- | --- | --- |
| `OnPlannerCompleteTask` | `OnCompleteTask_V3` | `groupId`, `id` |
| `OnPlannerNewTask` | `OnNewTask_V3` | `groupId`, `id` |
| `OnPlannerTaskAssignedToMe` | `OnTaskAssignedToMe_V2` | None; uses the connected user |

`id` means **plan ID**, not task ID. Group and plan IDs must belong to resources the consenting Microsoft 365 account can access. The completed/new-task operations use GET routes under `/v2/v1.0/planner/.../plans/{id}/tasks`; assigned-to-me uses `/v1.0/me/planner/ontaskassignedtome_trigger/tasks`.

## Reviewed source contract

The operation names, required keys and function names match the Node Planner webhook reference at commit `158d7e9944caa99f12ec481f1a837320720916d6`, its operation-request resolver and README, and Python `azure.connectors.planner.TRIGGER_OPERATIONS`. The SDK trigger metadata is not a callable client-method surface. The extension's `GetTaskResponseV2` wrapper delegates list deserialization to the generated Planner SDK task model.

Swagger declares a Group Id dynamic selector through `ListGroups`. Plan Id uses `ListGroupPlans` with the selected `groupId`. These samples **do not implement automated pickers**. Supply real IDs in the mode's ignored trigger-input file or enter them at the prompts. The assigned-to-me trigger needs neither ID. Only the reviewed required keys are accepted; optional or guessed wire parameters are rejected.

## Setup and safety

Both projects use the connector-local [setup helper](scripts/setup.py); neither depends on another sample. Use a distinct azd environment for each mode. Do not point both environments at the same resource group. The templates create Python 3.14 Flex Consumption (`FC1`) apps with no always-ready instances, system-assigned identity, AVM storage and monitoring, Entra-only monitoring ingestion, and namespace/function/deployer connection policies. Blob, queue and table host-storage access uses managed identity. Function roles are assigned after the app exists. No FIC, client credentials or cloud `FUNCTIONS_WORKER_RUNTIME` setting is used.

Bicep creates infrastructure, **not trigger configs**. All three listeners start disabled; polling decorators have the future config names from provisioning but no fabricated polling URL. The postdeploy hook validates inputs, preserves existing OAuth consent or invokes `connection authenticate --timeout 300 --no-access-policy`, and verifies `Connected` before any writes. Authentication inherits the normal terminal: keep it open, complete the browser flow, and answer the CLI's visible prompts. Do not redirect, capture or publish the OAuth transcript; it can contain consent details. A timeout is a failure, not authorization.

The hook checks every existing same-name resource's metadata, ID, operation, connection and mode before changing any source. Names use the connection prefix plus mode and function name. Foreign sources stop setup. Trigger pagination follows only bounded, non-repeated URLs in the same ARM collection. Every Azure CLI command pins the subscription from the selected azd environment.

Before registration the hook disables all listeners and verifies their settings. It creates selected sources, waits for successful provisioning, disables deselected **owned** sources by changing only state, and never deletes sources. Reruns reuse unchanged configs; updates preserve writable metadata, recurrence and other properties while stripping read-only fields. A failure leaves listeners disabled. After all sources verify, it enables only selected listeners and verifies the settings again. This is not an atomic multi-resource transaction: a failed run can leave registered sources with disabled listeners; rerun after fixing the cause.

Settings and callback keys go through private JSON files, with current-user Windows ACLs or POSIX permissions and cleanup on every exit. Noninteractive command output is captured; helper errors never include keys, source IDs, app settings or callback authentication. Interactive OAuth output belongs to the CLI and remains visible in the terminal. A new local settings file is private and atomic. Existing bytes remain unchanged unless the hook receives `--force` (PowerShell `-Force`). Never commit real local settings or trigger inputs. The checked-in examples contain no secrets and placeholder IDs are deliberately rejected.

## Validation limits

Offline validation can check the Python handlers and actual helper using mock CLI responses, Bicep compilation, PowerShell/Bash syntax, and the official azd YAML schema. It does not prove cloud support, OAuth permissions, host startup with disabled listeners, source registration or live event delivery. **No live deployment or event delivery was verified for these samples.** Connector Gateway preview resource types may produce Bicep `BCP081` warnings because the compiler lacks their schemas.