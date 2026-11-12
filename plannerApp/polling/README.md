# Planner polling events

This standalone app receives completed-task, new-task and assigned-to-me events as typed lists. Each handler logs only its trigger name and item count. See the [operation contract and safety rules](../README.md).

## Build and deploy

Install Python 3.14, Azure Functions Core Tools v4 with Preview connector-bundle support, Azure CLI with a `connector-namespace` extension that supports `connection authenticate`, Azure Developer CLI, and Azurite for local development. The deployed app always uses Python 3.14. The requirements select Functions SDK `>=2.4.0b1` for Python 3.13+ and `>=1.27.0b1` for older local runtimes; the connector extension requires `>=1.0.0b4`.

From this directory, create a virtual environment, activate it, and install [requirements](requirements.txt) with pip's `--pre` option. Sign in with Azure CLI and azd, select your intended subscription, and create a unique azd environment. Set `AZURE_LOCATION`, and optionally `CONNECTOR_NAMESPACE_LOCATION` (default `westcentralus`) and `APPLICATION_INSIGHTS_LOCATION` to supported regions. Provisioning grants the signed-in deployer access for local testing.

Copy [trigger-inputs.example.json](trigger-inputs.example.json) to ignored trigger-inputs.json, replace every selected placeholder with an actual Group Id and Plan Id, and remove objects for unselected events. Do not change the reviewed function/operation pairs. Assigned-to-me may be the only selected entry and uses an empty parameter array. Empty arrays, duplicate events, unknown operations, wrong keys and placeholder values fail before source writes.

Alternatively, leave the file absent and answer configure/skip prompts. Enter real IDs when asked, or supply `PLANNER_GROUP_ID` and `PLANNER_PLAN_ID` in the source environment. `PLANNER_TRIGGER_INPUTS` can hold the complete reviewed JSON array. File input takes precedence over that environment variable. No interactive dynamic picker runs. At least one event must remain selected.

Run `azd up` here. After provisioning and code deployment, the interactive postdeploy hook completes OAuth, verifies the connection, registers **Poll** configs and retrieves their receive URIs from the service. Keep the normal terminal open for the CLI's visible authentication prompts and complete browser consent; do not redirect or publish that transcript. No trigger creation runs during Bicep deployment or before consent. The service URI must use HTTPS and the expected trigger/gateway path, and all selected triggers must agree on the gateway. There is no fabricated fallback endpoint.

The hook sets `ConnectorNamespace__pollingEndpoint` and all three `FunctionTriggerConfigName` values, then enables only selected functions. The decorator uses `connection="ConnectorNamespace"`, `DeliveryMode.POLL` and `%FunctionTriggerConfigName%`. No webhook key or callback is used.

To retry, run `azd hooks run postdeploy` from this directory. To use another input file, call [postdeploy.ps1](infra/scripts/postdeploy.ps1) with `-InputsFile`, or [postdeploy.sh](infra/scripts/postdeploy.sh) with `--inputs`. To replace existing local settings, use `-Force` or `--force`. Reruns preserve consent, reuse unchanged sources and disable deselected owned sources without deleting them.

## Local run and live checks

The hook creates ignored local settings with Azurite storage, Python worker isolation, developer authentication and the service's real polling endpoint. Existing local settings remain untouched by default. The [local settings example](local.settings.example.json) starts all listeners disabled and is only a bootstrap example, not a configured Poll app. After consent and source creation, use the hook-generated settings, or explicitly force regeneration.

Start Azurite and run `func start` in the activated environment. Local polling uses the deployer's Azure login and connection policy. A single Poll source is a queue consumer: stop the deployed listeners before local testing, or use a separate environment/connection and its generated settings. Do not assume cloud and local consumers each receive a copy. The helper does not stop the cloud app for you.

Check the connection is `Connected`, selected configs are `Enabled`, and unselected owned configs/listeners are `Disabled`. Create a task, complete a task, or assign a task to the consenting user, then inspect name/count logs. No source IDs or task content should appear. If setup fails, leave listeners disabled, fix consent, permissions, region or input issues, and rerun the hook.

**No live deployment, host startup or event delivery was verified.** Offline compilation and mock execution do not establish those results.