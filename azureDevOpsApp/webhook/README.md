# Azure DevOps webhook triggers

Copy this directory on its own. Its infrastructure, hooks, standard-library helper [infra/scripts/setup.py](infra/scripts/setup.py), ignore rules and setup guidance are all local. This app receives Connector Namespace callbacks, not raw Azure DevOps service-hook envelopes.

| Function | Connector operation | Event |
|---|---|---|
| `OnAzureDevOpsBuildCompleted` | `OnBuildCompleted` | Build completed |
| `OnAzureDevOpsGitPullClosed` | `OnGitPullClosed` | Pull request closed |
| `OnAzureDevOpsGitPullCreated` | `OnGitPullCreated` | Pull request created |
| `OnAzureDevOpsGitPush` | `OnGitPush` | Git push |
| `OnAzureDevOpsTfvcCheckIn` | `OnTfvcCheckIn` | TFVC check-in |
| `OnAzureDevOpsWorkItemAssigned` | `OnWorkItemAssignedV2` | Work item assigned |
| `OnAzureDevOpsWorkItemClosed` | `OnWorkItemClosedV2` | Work item closed |
| `OnAzureDevOpsWorkItemCreated` | `OnWorkItemCreatedV2` | Work item created |
| `OnAzureDevOpsWorkItemUpdated` | `OnWorkItemUpdatedV2` | Work item updated |

## Runtime and dependencies

The nine handlers in [function_app.py](function_app.py) import `List` from `typing`. They use `List[devops.BuildResult]`, `List[devops.GitPullRequest]`, `List[devops.GitPush]`, `List[devops.TfvcChangeset]` or `List[devops.TriggerWorkItemResponse]` from `azurefunctions.extensions.connectors.visualstudioteamservices`. They log only event names/counts and return `None`; never log fields or return payloads.

Install [requirements.txt](requirements.txt) in an activated virtual environment. It selects `azure-functions>=1.27.0b1` below Python 3.13 and `azure-functions>=2.4.0` for Python 3.13+. Use pip's `--pre` option if needed for the older-runtime prerelease. The only connector requirement is `azurefunctions-extensions-connectors>=1.0.0`; its dependency supplies the SDK, so no direct `azure-connectors` requirement is needed. Local Values require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, as the example and generator provide. Add it to existing settings or request a force refresh.

Cloud infrastructure uses Python 3.14 Flex Consumption. [host.json](host.json) uses standard `Microsoft.Azure.Functions.ExtensionBundle` range `[4.41.2, 5.0.0)`, not the preview bundle. Verify installed wheels contain these Azure DevOps bindings; offline checks against local source do not prove published-wheel contents.

## Permissions and prerequisites

- Install Python, Azure Functions Core Tools v4, Azurite, Azure CLI (Windows: MSI), native Azure Developer CLI, and the Azure CLI `connector-namespace` extension with `connection authenticate` support. Windows hooks use PowerShell and Python; POSIX hooks use `sh` and `python3`.
- Sign in with `az login` and `azd auth login` and select the same subscription. The deployer needs resource creation and role-assignment write rights, such as Contributor plus Role Based Access Control Administrator at the target scope. Register Microsoft.Web, Microsoft.Storage, Microsoft.Insights and Microsoft.OperationalInsights if necessary.
- The Azure DevOps organization must allow the connector's Entra application and consent under its tenant policy. Sign in with an account in the organization's home tenant; user connections only list organizations in that tenant. The account needs organization/project access and permission to create/manage service-hook subscriptions, plus read access to selected builds, Git repositories, TFVC and work items. Consent does not grant missing source permissions. Review the [connector reference](https://learn.microsoft.com/connectors/visualstudioteamservices/) and [service-hook permissions](https://learn.microsoft.com/azure/devops/service-hooks/overview?view=azure-devops#permissions).
- Choose an app region supporting Python 3.14 Flex Consumption. Connector Namespace defaults to `brazilsouth`; change `CONNECTOR_NAMESPACE_LOCATION` only to a supported preview region exposing these operations.

## Configure and deploy

Run from this directory in an interactive terminal:

```bash
az login
azd auth login
azd env new azuredevops-webhook
azd up
```

Use a new environment rather than reusing an old `vstsApp` deployment. Existing `OnVsts` trigger configurations are not migrated or disabled automatically; stop old apps and disable old triggers separately to avoid duplicate subscriptions.

After deploying the app, the postdeploy hook completes EntraOAuth consent. Choose **Configure** or **Skip** for each event; at least one must be configured. The helper uses live connector metadata and authenticated pickers for required organizations, projects, repositories, teams and members. Inputs without a picker are entered manually; optional filters use connector defaults. It validates the selection, checks the app hostname and `connector_extension` system key, then preflights ownership and registers callbacks. Skipped listeners remain disabled.

Selections are saved in the azd environment as `AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS` and reused on rerun. An optional ignored `trigger-inputs.json` can bypass interactive selection, not consent or validation: copy [trigger-inputs.example.json](trigger-inputs.example.json), keep a nonempty subset and replace every placeholder. Use exact wire keys such as `wiql__System_AssignedTo`; `account` is an organization name, not a URL. Do not enter tokens or callback keys.

Ordinary CLI calls time out after 120 seconds; browser authentication after 660 seconds. Windows invokes the Azure CLI MSI's interpreter directly to avoid cmd.exe expansion. Request JSON and setting updates use private `@file` arguments. Callback secrets never appear in command arguments or logs. Both shell hooks use the local helper, with no parent file dependency.

## Infrastructure, ownership and reruns

Infrastructure creates a resource group, Python 3.14 FC1 Linux Function App, managed-identity host/package storage, Entra-authenticated Application Insights and Connector Namespace. Shared keys are disabled, `alwaysReady` is empty, and cloud settings omit `FUNCTIONS_WORKER_RUNTIME`. Developer and app identities receive connection policies; there is no namespace self-access policy. The app/deployer receive Storage Blob Data Owner, Queue Data Contributor, Table Data Contributor and monitoring access. [infra/function-access.bicep](infra/function-access.bicep) waits for the app identity.

The deterministic connection ends in `-entra`, avoiding unsupported in-place mutation of legacy OAuth. Bicep creates no webhook trigger configs. New listeners start disabled. Reprovision merges existing settings so unrelated settings, runtime connection values and previously selected listener flags survive; postdeploy applies the reviewed selection.

Before its first trigger or settings write, the helper follows bounded same-collection HTTPS pagination, including empty pages, and verifies all matching configs' full IDs, operations, connection, delivery mode and app-owner metadata. Conflicts stop the entire plan. It pauses all listeners, registers selected callbacks, disables only owned deselected configs, and enables selected listeners only after every registration succeeds. It preserves writable recurrence/metadata, excludes read-only fields from PUT bodies and avoids PUT for unchanged sources. It never deletes configs or touches unrelated sources.

Callbacks use the actual app DNS hostname plus `/runtime/webhooks/connector?functionName={function}`. Notification authentication adds `code` using the `connector_extension` **system** key, not a function key or host master key. Keys stay in private temporary request bodies, never local settings or azd outputs. Hostnames must be DNS names, not IPs; credentials, alternate ports, fragments and unsafe continuation collections are rejected.

Pending resources receive bounded retries; failed states or timeouts stop setup. Registration failure leaves listeners paused. Resolve consent, schemas, source permissions, ownership or host startup, then run `azd hooks run postdeploy`. To choose again, remove the optional input file if present and run:

```bash
azd env set AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS ""
azd hooks run postdeploy
```

A late local-settings failure does not roll back completed cloud registration.

## Local testing and private files

Postdeploy creates `local.settings.json` with the connection URL and listener settings, preserving an existing file. To refresh it, run [infra/scripts/postdeploy.ps1](infra/scripts/postdeploy.ps1) with `-ForceLocalSettings`, or [infra/scripts/postdeploy.sh](infra/scripts/postdeploy.sh) with `--force-local-settings`.

Sign in with `az login`, start Azurite in a separate terminal, then install the requirements and start the host:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

Starting a local host does **not** redirect cloud callbacks. Expose port 7071 through a public HTTPS tunnel and create a separate trigger configuration in [Connector Namespaces](https://connectors.azure.com/) with callback `https://<tunnel-host>/runtime/webhooks/connector?functionName=<FunctionName>` and the **local** `connector_extension` system key as the `code` query parameter. Core Tools stores that local key in Azurite's `azure-webjobs-secrets`; do not use the cloud app's key. Disable or delete the local trigger configuration when finished.

Generated settings and temporary request directories use a protected current-user-token-only Windows ACL or owner-only POSIX permissions. Windows explicitly imports `ctypes.wintypes`, uses the token's SID and removes broad inherited grants. Permission failures stop setup. Cleanup runs on success/failure; atomic replacement failure leaves old settings intact. Callback keys never enter local settings. Local ignore rules exclude settings, inputs and temporary artifacts as appropriate.

Create a selected Azure DevOps event and check its name/count log in the deployed or locally configured app for a live test.

Offline checks should pass actual `typing.List` annotations to `ConnectorConverter`, assert nested SDK fields, and check `None` results and count-only logs. The contract includes single-item `body` and `body.value` arrays. Empty batches log zero; malformed JSON and invalid arrays must fail conversion. Direct Azure DevOps envelopes with `eventType` and `resource` need separate normalization.

## Cleanup and limits

Removing an event disables its owned config/listener on the next hook run. It does not guarantee removal of upstream service-hook subscriptions. Review old connections and callbacks, especially after migrating legacy OAuth to the distinct `-entra` connection, before `azd down`. No unowned resource is deleted.

The nine-event inventory matches the TypeScript Azure DevOps sample; required inputs come from live connector metadata. Regional availability, live consent, bundle startup and callback delivery still need validation in a supported preview region.