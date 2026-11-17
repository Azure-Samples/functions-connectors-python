# Azure DevOps webhook triggers

Copy this directory on its own. Its infrastructure, hooks, standard-library helper [infra/scripts/setup.py](infra/scripts/setup.py), ignore rules and setup guidance are all local. This app receives Connector Namespace callbacks, not raw Azure DevOps service-hook envelopes.

| Function | Connector operation | Required wire keys |
|---|---|---|
| `OnVstsBuildCompleted` | `OnBuildCompleted` | `account`, `project` |
| `OnVstsGitPullClosed` | `OnGitPullClosed` | `account`, `project`, `repository` |
| `OnVstsGitPullCreated` | `OnGitPullCreated` | `account`, `project`, `repository` |
| `OnVstsGitPush` | `OnGitPush` | `account`, `project`, `repository` |
| `OnVstsTfvcCheckIn` | `OnTfvcCheckIn` | `account`, `project` |
| `OnVstsWorkItemAssigned` | `OnWorkItemAssignedV2` | `account`, `project`, `team`, `wiql__System_AssignedTo` |
| `OnVstsWorkItemClosed` | `OnWorkItemClosedV2` | `account`, `project` |
| `OnVstsWorkItemCreated` | `OnWorkItemCreatedV2` | `account`, `project` |
| `OnVstsWorkItemUpdated` | `OnWorkItemUpdatedV2` | `account`, `project` |

## Runtime and dependencies

The nine handlers in [function_app.py](function_app.py) import `List` from `typing`. They use `List[devops.BuildResult]`, `List[devops.GitPullRequest]`, `List[devops.GitPush]`, `List[devops.TfvcChangeset]` or `List[devops.TriggerWorkItemResponse]` from `azurefunctions.extensions.connectors.visualstudioteamservices`. They log only event names/counts and return `None`; never log fields or return payloads.

Install [requirements.txt](requirements.txt) in an activated virtual environment. It selects `azure-functions>=1.27.0b1` below Python 3.13 and `azure-functions>=2.4.0` for Python 3.13+. Use pip's `--pre` option if needed for the older-runtime prerelease. The only connector requirement is `azurefunctions-extensions-connectors>=1.0.0`; its dependency supplies the SDK, so no direct `azure-connectors` requirement is needed. Local Values require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, as the example and generator provide. Add it to existing settings or request a force refresh.

Cloud infrastructure uses Python 3.14 Flex Consumption. [host.json](host.json) uses standard `Microsoft.Azure.Functions.ExtensionBundle` range `[4.41.2, 5.0.0)`, not the preview bundle. Verify installed wheels contain these Azure DevOps bindings; offline checks against local source do not prove published-wheel contents.

## Permissions and prerequisites

- Install Python, Azure Functions Core Tools v4, Azurite, Azure CLI (Windows: MSI), native Azure Developer CLI, and the Azure CLI `connector-namespace` extension with `connection authenticate` support. Windows hooks use PowerShell and Python; POSIX hooks use `sh` and `python3`.
- Sign in with `az login` and `azd auth login` and select the same subscription. The deployer needs resource creation and role-assignment write rights, such as Contributor plus Role Based Access Control Administrator at the target scope. Register Microsoft.Web, Microsoft.Storage, Microsoft.Insights and Microsoft.OperationalInsights if necessary.
- The Azure DevOps organization must allow the connector's Entra application and consent under its tenant policy. The signed-in source account needs organization/project access and permission to create/manage service-hook subscriptions, plus read access to selected builds, Git repositories, TFVC and work items. Assigned-work-item events also need the selected team and assignee. Consent does not grant missing source permissions. Review the [connector reference](https://learn.microsoft.com/connectors/visualstudioteamservices/) and [service-hook permissions](https://learn.microsoft.com/azure/devops/service-hooks/overview?view=azure-devops#permissions).
- Choose an app region supporting Python 3.14 Flex Consumption. Connector Namespace defaults to `brazilsouth`; change `CONNECTOR_NAMESPACE_LOCATION` only to a supported preview region exposing these operations.

## Configure and deploy

1. Open a terminal here and run `azd init` with an environment name distinct from any polling deployment.
2. Copy [trigger-inputs.example.json](trigger-inputs.example.json) to the ignored mode-local file named trigger-inputs.json. Keep a nonempty subset and replace all placeholders. Each object has `functionName`, `operationName` and a `parameters` array of `{ "name": "wire-key", "value": "reviewed-string" }`. Do not enter tokens or callback keys.
3. Use exact wire keys from the table. `account` means organization name, not a URL. Obtain actual project, repository, team and assignee identifiers from Azure DevOps or documented connector selectors. Preserve `wiql__System_AssignedTo`, not Python-normalized spelling. Optional filters must match live exported schemas. This mode uses reviewed input files, not interactive source selection.
4. Run `azd up`. Preprovision validates structure and known required keys before any CLI call. It then inventories the existing app and sets an existence flag. Inventory errors stop provisioning, rather than treating denied reads as absence. [infra/main.bicep](infra/main.bicep) reads existing app settings before its resource module runs and passes them securely for merging.
5. After infrastructure and code deployment, the local helper reads the connection and verifies EntraOAuth on every read. Unless already Connected, it runs `az connector-namespace connection authenticate` with the provisioned subscription, `--timeout 300` and `--no-access-policy` directly in the terminal. Complete browser consent and keep the terminal open. The next read must report Connected and EntraOAuth. No source is created before consent.
6. The helper exports live Swagger, resolves local parameter references and validates strings, required values, bounds, enums, patterns and optional filters. Unknown keys, duplicates and unsupported schemas stop setup before configuration writes. It checks the actual app hostname, waits for the `connector_extension` system key, then preflights ownership and registers callbacks.

Ordinary CLI calls time out after 120 seconds; browser authentication after 660 seconds. Windows invokes the Azure CLI MSI's interpreter directly to avoid cmd.exe expansion. Request JSON and setting updates use private `@file` arguments. Callback secrets never appear in command arguments or logs. Both shell hooks use the local helper, with no parent file dependency.

## Infrastructure, ownership and reruns

Infrastructure creates a resource group, Python 3.14 FC1 Linux Function App, managed-identity host/package storage, Entra-authenticated Application Insights and Connector Namespace. Shared keys are disabled, `alwaysReady` is empty, and cloud settings omit `FUNCTIONS_WORKER_RUNTIME`. Developer and app identities receive connection policies; there is no namespace self-access policy. The app/deployer receive Storage Blob Data Owner, Queue Data Contributor, Table Data Contributor and monitoring access. [infra/function-access.bicep](infra/function-access.bicep) waits for the app identity.

The deterministic connection ends in `-entra`, avoiding unsupported in-place mutation of legacy OAuth. Bicep creates no webhook trigger configs. New listeners start disabled. Reprovision merges existing settings so unrelated settings, runtime connection values and previously selected listener flags survive; postdeploy applies the reviewed selection.

Before its first trigger or settings write, the helper follows bounded same-collection HTTPS pagination, including empty pages, and verifies all matching configs' full IDs, operations, connection, delivery mode and app-owner metadata. Conflicts stop the entire plan. It pauses all listeners, registers selected callbacks, disables only owned deselected configs, and enables selected listeners only after every registration succeeds. It preserves writable recurrence/metadata, excludes read-only fields from PUT bodies and avoids PUT for unchanged sources. It never deletes configs or touches unrelated sources.

Callbacks use the actual app DNS hostname plus `/runtime/webhooks/connector?functionName={function}`. Notification authentication adds `code` using the `connector_extension` **system** key, not a function key or host master key. Keys stay in private temporary request bodies, never local settings or azd outputs. Hostnames must be DNS names, not IPs; credentials, alternate ports, fragments and unsafe continuation collections are rejected.

Pending resources receive bounded retries; failed states or timeouts stop setup. Registration failure leaves listeners paused. Resolve consent, schemas, source permissions, ownership or host startup, then run `azd hooks run postdeploy`. Update the input file to change sources. A late local-settings failure does not roll back completed cloud registration.

## Local testing and private files

Postdeploy atomically creates the ignored local settings file from [local.settings.example.json](local.settings.example.json), preserving existing bytes by default. Refresh using [infra/scripts/postdeploy.ps1](infra/scripts/postdeploy.ps1) with `-ForceLocalSettings`, or [infra/scripts/postdeploy.sh](infra/scripts/postdeploy.sh) with `--force-local-settings`. Refresh retains unrelated Values, adds `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` and removes local managed-identity credentials. Sign in as the developer with connection access, keep Azurite running for `UseDevelopmentStorage=true`, install requirements and run `func start`.

Generated settings and temporary request directories use a protected current-user-token-only Windows ACL or owner-only POSIX permissions. Windows explicitly imports `ctypes.wintypes`, uses the token's SID and removes broad inherited grants. Permission failures stop setup. Cleanup runs on success/failure; atomic replacement failure leaves old settings intact. Callback keys never enter local settings. Local ignore rules exclude settings, inputs and temporary artifacts as appropriate.

Starting a local host does **not** redirect cloud callbacks; this sample creates no public tunnel. Create a selected Azure DevOps event and check its name/count log in the deployed app for a live test.

Offline checks should pass actual `typing.List` annotations to `ConnectorConverter`, assert nested SDK fields, and check `None` results and count-only logs. The contract includes single-item `body` and `body.value` arrays. Empty batches log zero; malformed JSON and invalid arrays must fail conversion. Direct Azure DevOps envelopes with `eventType` and `resource` need separate normalization.

## Cleanup and limits

Removing an event disables its owned config/listener on the next hook run. It does not guarantee removal of upstream service-hook subscriptions. Review old connections and callbacks, especially after migrating legacy OAuth to the distinct `-entra` connection, before `azd down`. No unowned resource is deleted.

The inventory follows Node webhook revision `158d7e9944caa99f12ec481f1a837320720916d6`; required keys follow Python metadata revision `ef2011621f4ad64838a8a18c5720aef840fdfe46`. Offline tests do not prove published packages, regional availability, live consent, bundle startup or callback delivery. These still need validation in a supported preview region.