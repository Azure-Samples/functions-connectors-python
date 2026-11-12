# Planner webhook events

This standalone app receives completed-task, new-task and assigned-to-me events as typed lists. Each handler logs only its trigger name and item count. See the [operation contract and safety rules](../README.md).

## Build and deploy

Install Python 3.14, Azure Functions Core Tools v4 with Preview connector-bundle support, Azure CLI with a `connector-namespace` extension that supports `connection authenticate`, Azure Developer CLI, and Azurite for local development. The cloud app always uses Python 3.14. Requirements select Functions SDK `>=2.4.0b1` for Python 3.13+ and `>=1.27.0b1` for older local runtimes; the connector extension requires `>=1.0.0b4`.

From this directory, create and activate a virtual environment and install [requirements](requirements.txt) with pip's `--pre` option. Sign in with Azure CLI and azd, select the subscription and create a unique azd environment. Set `AZURE_LOCATION`, and optionally `CONNECTOR_NAMESPACE_LOCATION` (default `westcentralus`) and `APPLICATION_INSIGHTS_LOCATION` to supported regions.

Copy [trigger-inputs.example.json](trigger-inputs.example.json) to ignored trigger-inputs.json, replace placeholders with actual Group Id and Plan Id, and remove unselected objects. The `id` key means plan ID, not task ID. Assigned-to-me uses the consenting user and requires an empty parameter array. Each entry must use the exact reviewed function/operation pair and parameter keys. Empty selections, duplicates, unknown keys and placeholders fail before source writes.

If no file exists, the hook prompts configure/skip for each event and asks for real IDs. `PLANNER_GROUP_ID` and `PLANNER_PLAN_ID` can supply those IDs, and `PLANNER_TRIGGER_INPUTS` can supply the complete JSON array. File input wins over the environment array. This sample does not automate dynamic pickers. Select at least one event.

Run `azd up` here. All listeners start disabled. After deploying code, the interactive hook completes OAuth if needed, verifies `Connected`, and obtains the **connector_extension system key**, not a host/function key. Keep the normal terminal open for visible CLI prompts and complete browser consent; do not redirect or publish that transcript. The helper captures noninteractive key/settings commands. It uses the actual deployed hostname for `/runtime/webhooks/connector?functionName=...`. The callback key stays in `notificationDetails.authentication` with `type=QueryString`, `name=code`; the helper never prints it or adds it to the callback URL.

Webhook decorators use the default delivery mode, with no Poll-only fields. Config names use the connection-specific webhook prefix. The hook verifies ownership, registers selected sources, disables deselected owned sources without deleting them, and enables only selected listeners after successful source/settings verification. Bicep creates no trigger configs. Reruns preserve consent and reuse unchanged resources.

Retry with `azd hooks run postdeploy` here. [postdeploy.ps1](infra/scripts/postdeploy.ps1) accepts `-InputsFile` and `-Force`; [postdeploy.sh](infra/scripts/postdeploy.sh) accepts `--inputs` and `--force`. These wrappers use only the [connector-local helper](../scripts/setup.py).

## Local run and live checks

The hook writes private ignored local settings for Azurite and the Python worker, preserving any existing file by default. You can also start from the [disabled local settings example](local.settings.example.json). Start Azurite and run `func start` in the activated environment to index the typed handlers.

Running locally does **not** register or retarget live callbacks. The automated hook always targets the deployed app's actual hostname and key. Live local webhook testing needs a reachable HTTPS origin, the local connector extension system key, and a separately owned subscription created through Connector Namespaces with `uriQuery`/QueryString authentication. Keep the key in authentication metadata, never logs or source control. Do not retarget the deployed sample's source or use a cloud extension key for a local host. This sample does not automate local tunnels or local callback registration.

Check the connection is `Connected`, selected sources are `Enabled`, and deselected owned sources/listeners are `Disabled`. Create, complete or assign a task as appropriate; inspect trigger-name/count logs. Check source registration and connection permissions if no event arrives. A failed or partial hook run keeps listeners disabled; fix the cause and retry.

**No live deployment, host startup, OAuth or event delivery was verified.** Offline validation does not prove those behaviors.