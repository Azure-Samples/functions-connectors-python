# Azure DevOps polling triggers

This standalone Azure Functions Python project uses Connector Namespace **Poll delivery** for the nine events below. Poll delivery describes how the Function App receives queued connector events; it does not change Azure DevOps's source-event semantics.

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

All handlers in [function_app.py](function_app.py) take raw `str`, log the trigger name only, and return `None`. Do not deserialize the payload or return it as a callback response.

## Prepare before provisioning

1. Install Python 3.14, Azure Functions Core Tools, Azure Developer CLI (`azd`), Azure CLI, and the `connector-namespace` CLI extension with `connection authenticate` support. Use an account allowed to create resources and role assignments. Azure DevOps must allow the connector's Entra application and the selected account must have access to the organization, projects, repositories, and work items.
2. Open a terminal in this polling project. Sign in with Azure CLI and azd, choose the subscription, and initialize a distinct environment with `azd init`. Choose a region that supports Python 3.14 Flex Consumption. Connector Namespace defaults to `brazilsouth`; change `CONNECTOR_NAMESPACE_LOCATION` only to a preview region that exposes these operations.
3. Copy [trigger-inputs.example.json](trigger-inputs.example.json) to the ignored mode-local file named trigger-inputs.json. Keep only the event objects you want. A nonempty subset is valid; omitted events remain disabled. Replace every placeholder with reviewed organization/project and selector values. Do not put tokens or callback keys in this file.
4. Review the [Azure DevOps connector reference](https://learn.microsoft.com/connectors/visualstudioteamservices/) for organization access and selector meaning. `account` is the organization name, not its full URL. Obtain project, repository, team, and assignee values from your Azure DevOps resources or the connector's documented selectors. Use the exact wire keys above, not Python-normalized names such as `wiql_system_assigned_to`. Optional parameters must come from the actual exported operation schema. The helper does **not** automate picker calls or guess unknown wire keys.
5. Run `azd up` from this project. The preprovision hook checks input structure, parameter entries, and known required wire keys locally, before any CLI call. The postdeploy hook authenticates, exports connector Swagger, resolves local parameter references, and validates strings, bounds, enums, patterns, and any optional filters before writing any trigger or settings plan.

The example is a reviewed wire-key template, not a usable source selection until you replace its values. The hook passes your exact `parameters` array through to the trigger-config API. Unsupported schema types, missing keys, unknown parameters, and duplicate entries stop setup rather than silently dropping filters.

Selection does not prompt, including in noninteractive runs. Missing required keys name the function and wire keys in the error. For example, an assigned-work-item selection needs `team` and `wiql__System_AssignedTo` as well as `account` and `project`. Correct the input file and rerun; the helper never guesses selector values. Full validation of optional filters requires the exported Swagger after consent.

The CLI wrapper limits ordinary requests to 120 seconds and browser authentication to 660 seconds. On Windows, use the Azure CLI MSI and a native azd executable. The helper invokes the MSI's own Python interpreter directly instead of passing arguments through cmd.exe. JSON request bodies and settings use `@file` arguments; ampersands, percent signs, quotes, and spaces remain argument data. The interactive hook gives browser consent the terminal; ordinary CLI output remains captured and secrets are never printed.

## Provisioning and registration

[infra/main.bicep](infra/main.bicep) provisions only infrastructure: a resource group, FC1 Linux Function App running Python 3.14, storage, Entra-authenticated Application Insights, Connector Namespace, and a distinct deterministic connection ending in `-entra`. [infra/function-access.bicep](infra/function-access.bicep) grants the Function App storage Blob Data Owner, Queue Data Contributor, Table Data Contributor, monitoring access, and connection access after its identity exists. The namespace and deployer also receive connection access; the deployer receives storage and monitoring roles. Host and deployment storage use managed identity, shared keys are disabled, and `alwaysReady` is empty. Cloud settings omit `FUNCTIONS_WORKER_RUNTIME`.

All cloud listeners start disabled. Bicep creates **no trigger configs**. The [shared hook](../scripts/setup.py) reads the provisioned connection and checks `parameterValueSet.name == EntraOAuth` on every read. For a non-Connected connection it invokes `az connector-namespace connection authenticate` with the provisioned subscription, a 300-second timeout, and `--no-access-policy`. This browser flow runs directly in the terminal, without capturing authentication output. Complete consent and leave the terminal open. The hook reads the connection again and requires Connected and EntraOAuth. It never uses legacy consent links.

Next the hook checks the actual app hostname, reads the full same-collection trigger inventory with a pagination cycle guard, and verifies every matching source's resource ID, operation, connection, mode, and app metadata **before any configuration write**. It pauses all listeners, registers or updates selected sources, and changes only owned omitted sources to Disabled. It does not delete sources. Unchanged trigger properties cause no PUT; updates retain writable recurrence and metadata fields and drop read-only provisioning and endpoint fields.

Pending connections and existing source registrations receive bounded reads before setup proceeds. Failed or timed-out registrations stop setup. Pagination rejects a different HTTPS origin or collection, malformed URLs, and case-only cycles. Polling origins reject IP addresses and malformed DNS labels; all selected endpoints must agree.

For every selected source the hook reads `pollingEndpoints.receiveUri` with a bounded wait. This public-cloud sample accepts only HTTPS origins under `logic.azure.com` or `connectornamespaces.azure.com`, with no credentials, alternate port, query, or fragment and the service's exact `/api/connectorGateways/{opaque-id}/triggerconfigs/{name}/receive` or dedicated-DNS `/api/triggerconfigs/{name}/receive` route. It derives the polling prefix from that response, never from the ARM namespace ID or an invented hostname, and requires all selected endpoints to agree. It never calls a returned receive URL during setup.

Only after all sources become ready does the hook set `ConnectorNamespace__credential=managedidentity`, `ConnectorNamespace__pollingEndpoint`, the nine trigger-config name settings, and each listener's disabled flag through a private JSON settings file. A failure during registration leaves listeners paused. Fix the source permission, schema, or runtime error and rerun `azd hooks run postdeploy` in this project. A later local-settings failure does not roll back completed cloud registration.

## Local testing

The hook creates the ignored local settings file atomically from [local.settings.example.json](local.settings.example.json). It preserves an existing file by default; to refresh it, invoke [infra/scripts/postdeploy.ps1](infra/scripts/postdeploy.ps1) with `-ForceLocalSettings` or [infra/scripts/postdeploy.sh](infra/scripts/postdeploy.sh) with `--force-local-settings`. Force merges values while retaining unrelated settings. Neither local template nor generated local connector settings request managed identity; sign in as the developer who has connection access. Keep Azurite running for `UseDevelopmentStorage=true`, install [requirements.txt](requirements.txt) in a virtual environment, and start the local host with `func start`.

Temporary request directories and generated local settings use a current-user-only Windows ACL or owner-only POSIX permissions. The Windows ACL uses the current token's SID, not a guessed account name. Permission failures stop setup. Temporary files are removed on success and failure; an atomic replacement failure preserves the old local settings.

Create source events for a selected operation and check the corresponding arrival log. Running cloud and local listeners on the same Poll trigger consumes the same queue, so stop one host when testing the other. No payloads or secrets appear in sample logs. [host.json](host.json) uses the preview extension bundle `[4.50.0, 5.0.0)`.

## Cleanup and limits

Omitting an event on a later hook run disables its owned trigger config and listener; it does not delete its Azure DevOps source subscription. Review old connections and old callback/source subscriptions manually, especially when replacing a legacy OAuth connection. The distinct `-entra` connection prevents an unsupported in-place OAuth migration, but cannot remove sources attached to the old connection. The hook never deletes unowned resources. Use `azd down` only after reviewing source cleanup and the environment's resources.

Polling registration of all nine operations is an adaptation of the pinned Node webhook inventory. Offline checks are not proof that each operation supports Poll delivery in your region or that an Azure DevOps event arrived. Live consent, provisioning, bundle startup, queue delivery, and acknowledgement remain deployment validation steps.