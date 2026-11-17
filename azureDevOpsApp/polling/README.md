# Azure DevOps polling triggers

Copy this directory on its own. It contains all infrastructure, hooks, ignore rules and the standard-library helper [infra/scripts/setup.py](infra/scripts/setup.py). Connector Namespace queues source events; the app receives and acknowledges them through **Poll delivery**, without a callback URL.

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

The nine handlers in [function_app.py](function_app.py) import `List` from `typing` and rich types from `azurefunctions.extensions.connectors.visualstudioteamservices`. They use `List[devops.BuildResult]`, `List[devops.GitPullRequest]`, `List[devops.GitPush]`, `List[devops.TfvcChangeset]` or `List[devops.TriggerWorkItemResponse]`. They log only event names and counts and return `None`; never log fields or return payloads.

Create and activate a virtual environment and install [requirements.txt](requirements.txt). It selects `azure-functions>=1.27.0b1` below Python 3.13 and `azure-functions>=2.4.0` for Python 3.13+. Use pip's `--pre` option if needed for the older-runtime prerelease. The only connector requirement is `azurefunctions-extensions-connectors>=1.0.0`; its dependency supplies the SDK, so no direct `azure-connectors` requirement is needed. Local Values require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, as the example and generator provide. Add it to existing settings or request a force refresh.

Cloud infrastructure uses Python 3.14 Flex Consumption. [host.json](host.json) uses standard `Microsoft.Azure.Functions.ExtensionBundle` range `[4.41.2, 5.0.0)`, not the preview bundle. Verify installed wheels contain the Azure DevOps bindings; local source-based checks do not prove published-wheel contents.

## Permissions and prerequisites

- Install Python, Azure Functions Core Tools v4, Azurite, Azure CLI (Windows: MSI), native Azure Developer CLI **1.33.0 or later**, and the Azure CLI `connector-namespace` extension with `connection authenticate` support. Windows hooks use PowerShell and Python; POSIX hooks use `sh` and `python3`.
- Sign in with `az login` and `azd auth login` and select the same subscription. The deployer needs resource creation and role-assignment write rights, such as Contributor plus Role Based Access Control Administrator at the target scope. Register Microsoft.Web, Microsoft.Storage, Microsoft.Insights and Microsoft.OperationalInsights if necessary.
- The Azure DevOps organization must allow the connector's Entra application and consent under its tenant policy. Sign in with an account in the organization's home tenant; user connections only list organizations in that tenant. The account needs organization/project access and permission to create/manage service-hook subscriptions, plus read access to selected builds, Git repositories, TFVC and work items. Consent does not grant missing source permissions. Review the [connector reference](https://learn.microsoft.com/connectors/visualstudioteamservices/) and [service-hook permissions](https://learn.microsoft.com/azure/devops/service-hooks/overview?view=azure-devops#permissions).
- Choose an app region supporting Python 3.14 Flex Consumption. Connector Namespace defaults to `brazilsouth`; change `CONNECTOR_NAMESPACE_LOCATION` only to a supported preview region exposing these operations.

## Provision in order

Run from this directory in an interactive terminal:

```bash
az login
azd auth login
azd env new azuredevops-polling
azd up
```

Use a new environment rather than reusing an old `vstsApp` deployment. Existing `OnVsts` trigger configurations are not migrated or disabled automatically; stop old apps and disable old triggers separately to avoid duplicate subscriptions.

[azure.yaml](azure.yaml) defines this order:

1. **Foundation**: [infra/main.bicep](infra/main.bicep) creates the resource group, managed-identity storage, telemetry, Flex plan, Connector Namespace and deterministic EntraOAuth connection ending in `-entra`. It reserves the future Function App name but creates neither an app nor trigger configs.
2. **Consent and validated selection**: the triggers layer's interactive preprovision hook checks the EntraOAuth connection and opens browser consent if needed. Choose **Configure** or **Skip** for each event; at least one must be configured. The helper uses live connector metadata and authenticated pickers for available organizations, projects, repositories, teams and members. Optional filters can be skipped. Inputs without a picker are entered manually and all selections are validated before source writes.
3. **Enabled poll configs**: the helper preflights ownership, registers selected configs with `deliveryMode=Poll` and `state=Enabled`, waits for readiness, and obtains their service-issued receive URIs. Their origins and route prefixes must agree. Only after every registration succeeds does it export the nonsecret endpoint and encoded listener settings to azd.
4. **App infrastructure**: the app layer's preprovision hook detects whether the app exists. [infra/app.bicep](infra/app.bicep) reads existing settings before the app module runs, then securely merges them with host settings, the validated polling endpoint, nine config-name settings and selected/deselected listener flags. It creates the Function App and its connection, storage and monitoring access. Poll registration needs no app.
5. **Code deploy**: azd deploys the package after app provisioning. Postdeploy only writes local settings; it does not register Poll sources again.

No input file is required. An optional ignored mode-local file named `trigger-inputs.json` bypasses interactive selection, not consent or validation. To use it, copy [trigger-inputs.example.json](trigger-inputs.example.json), keep a nonempty subset and replace every placeholder. Each object has `functionName`, `operationName` and a `parameters` array of `{ "name": "wire-key", "value": "reviewed-string" }`. Do not enter tokens or secrets. Otherwise, selections are saved in the azd environment as `POLLING_TRIGGER_INPUTS` and reused on rerun.

For an input file, `account` is an organization name, not a URL. Use exact wire keys such as `wiql__System_AssignedTo`, not Python-normalized names. Unknown keys, duplicates, unsupported schemas, missing required values and invalid enums, lengths or patterns stop setup before configuration writes.

## Ownership, settings and reruns

Before its first write, the helper reads the full trigger inventory through bounded same-collection HTTPS pagination, including empty pages. It preflights every matching event's full resource ID, operation, connection, delivery mode and app-owner metadata. Conflicts stop the entire plan. It disables only owned deselected configs, never unrelated sources, and never deletes configs. Updates retain writable recurrence and metadata fields and exclude read-only provisioning and endpoint fields. Unchanged sources need no PUT.

Pending resources receive bounded retries; failed states or timeouts stop the next layer. Receive URIs must match `/api/connectorGateways/{id}/triggerconfigs/{name}/receive` or `/api/triggerconfigs/{name}/receive` with HTTPS DNS, no credentials, alternate port, query or fragment. Setup derives the prefix from the service response, never the ARM ID, and never invokes the receive URL.

To choose again, remove the optional input file if present, clear the saved selection, and rerun the dependent layers:

```bash
azd env set POLLING_TRIGGER_INPUTS ""
azd provision triggers
azd provision app
azd deploy --all
```

Reprovision preserves unrelated app settings while replacing this sample's endpoint, config names and listener flags with validated values. Stop existing cloud/local consumers before changing a live selection if you need to avoid concurrent consumption or reconfiguration. A failed trigger run may leave some sources changed but prevents app provisioning from applying a partial plan. Correct the issue and rerun triggers before app provisioning; do not invoke the app layer alone after a failed trigger run.

The developer and Function App receive connection policies; the namespace receives no self-access policy. The app and deployer receive Storage Blob Data Owner, Queue Data Contributor, Table Data Contributor and monitoring access. Host/package storage use managed identity, shared keys are disabled, `alwaysReady` is empty, and cloud settings omit `FUNCTIONS_WORKER_RUNTIME`.

## Local testing and private files

Postdeploy atomically creates the ignored local settings file from [local.settings.example.json](local.settings.example.json), preserving existing bytes by default. Refresh using [infra/scripts/postdeploy.ps1](infra/scripts/postdeploy.ps1) with `-ForceLocalSettings`, or [infra/scripts/postdeploy.sh](infra/scripts/postdeploy.sh) with `--force-local-settings`. Refresh retains unrelated Values, adds `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` and removes local managed-identity credentials. Sign in as the developer with connection access, keep Azurite running for `UseDevelopmentStorage=true`, install requirements and run `func start`.

Temporary request directories and generated settings receive a protected current-user-token-only Windows ACL or owner-only POSIX permissions. Windows explicitly imports `ctypes.wintypes`, uses the token's SID and removes broad inherited grants. Permission failures stop setup. Request JSON uses private `@file` arguments. Temporary files are cleaned on success/failure; atomic replacement failure leaves old settings intact. Windows bypasses cmd.exe expansion. Ordinary CLI calls time out after 120 seconds; browser authentication after 660 seconds. Secrets and payloads never enter sample logs. Local ignore rules exclude settings, inputs and temporary artifacts as appropriate.

Generate a selected event and check its name/count log. Cloud and local Poll listeners compete for the same queue; stop one while testing the other. Offline checks should pass actual `typing.List` handler annotations to `ConnectorConverter`, assert nested SDK fields, and check `None` results and count-only logs. Item contracts include single items, arrays and Connector Namespace `body.value` batches; raw Azure DevOps envelopes with `eventType` and `resource` need separate normalization. Empty batches log zero; malformed JSON and invalid arrays must fail conversion.

## Cleanup and limits

Deselection disables owned configs/listeners; it does not guarantee deletion of upstream Azure DevOps subscriptions. Review old connections and source subscriptions before `azd down`, especially when replacing legacy OAuth with the distinct `-entra` connection. No unowned resource is deleted.

The nine-event inventory matches the TypeScript Azure DevOps sample; required inputs come from live connector metadata. Consent, live provisioning, bundle startup, event delivery and acknowledgement still need validation in a supported preview region. Offline checks do not establish end-to-end success.