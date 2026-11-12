# Azure DevOps webhook triggers

This standalone Azure Functions Python project receives Connector Namespace callbacks for nine events. It follows the Node webhook contract at revision `158d7e9944caa99f12ec481f1a837320720916d6`.

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

Handlers in [function_app.py](function_app.py) accept raw `str`, log only the trigger name, and return `None`. Unlike the Node sample, they do not return the payload. No connector SDK or Python connector extension package is needed for raw handlers.

## Prepare before provisioning

1. Install Python 3.14, Azure Functions Core Tools, Azure Developer CLI (`azd`), Azure CLI, and the `connector-namespace` CLI extension with `connection authenticate` support. Sign in using an account that can create resources and role assignments. Ensure the Azure DevOps organization allows the connector's Entra application and your account can access each selected project and source.
2. Open a terminal in this webhook project. Choose your subscription and run `azd init` with a distinct environment name, different from any polling deployment. Select a Function App region that supports Python 3.14 Flex Consumption. Connector Namespace defaults to `brazilsouth`; use another preview region only if it exposes the required connector operations.
3. Copy [trigger-inputs.example.json](trigger-inputs.example.json) to the ignored mode-local file named trigger-inputs.json. Keep a nonempty subset of events and replace every placeholder with reviewed values. Omitted events remain disabled. Do not enter tokens or callback keys in the input file.
4. Review the [Azure DevOps connector reference](https://learn.microsoft.com/connectors/visualstudioteamservices/) for selector meaning and permissions. `account` is the organization name, not its full URL. Get project, repository, team, and assignee identifiers from Azure DevOps or the connector's documented selectors. Keep the exact wire spelling `wiql__System_AssignedTo`. Optional parameters must match the exported operation schema. The helper does not offer an automatic picker or invent parameters.
5. Run `azd up` in this project. The preprovision hook checks that the reviewed input file exists and has the expected inventory structure. After deployment, the shared helper authenticates the connection, exports Swagger, resolves local parameter references, and validates the complete input array against the actual operation schemas before registering any source.

Each object has `functionName`, `operationName`, and a `parameters` array of `{ "name": "wire-key", "value": "reviewed-string" }`. Before any CLI call, the helper checks structure, distinct string parameters, and known required wire keys from the Python SDK metadata. After consent, it checks the exported Swagger's full schema, including optional filters, bounds, patterns, and enums, then passes the exact array through. Unsupported schemas or unknown wire keys stop setup before configuration writes. The example lists required keys, not working source values.

Selection never prompts, including in noninteractive runs. Missing keys name the selected function and required wire keys. For an assigned-work-item event, supply `team` and `wiql__System_AssignedTo` as well as `account` and `project`. Correct the JSON and rerun; the helper never guesses selector values. Only browser consent is interactive, and an already Connected EntraOAuth connection needs no prompt.

Ordinary CLI requests have a 120-second limit; browser authentication has a 660-second limit. Windows requires the Azure CLI MSI and a native azd executable. The helper invokes the MSI's Python interpreter directly, without cmd.exe argument expansion. JSON bodies and settings use `@file`; quotes, spaces, ampersands, and percent signs remain data. Both platform postdeploy hooks grant the consent process terminal access while the helper captures ordinary command output.

## Infrastructure and consent

[infra/main.bicep](infra/main.bicep) provisions a resource group, Python 3.14 FC1 Linux Function App, storage, Entra-authenticated Application Insights, and Connector Namespace. Deployment and host storage use managed identity with Blob Data Owner, Queue Data Contributor, and Table Data Contributor roles; shared keys are disabled. The namespace, deployer, and Function App receive connection access. [infra/function-access.bicep](infra/function-access.bicep) grants app access only after the app identity exists. The deployer also receives storage and monitoring roles. `alwaysReady` is empty and cloud settings omit `FUNCTIONS_WORKER_RUNTIME`.

The deterministic connection name ends in `-entra`. This creates a distinct EntraOAuth connection rather than attempting to mutate a legacy Azure DevOps OAuth connection in place. Bicep provisions no trigger configs, and all listeners start disabled.

The [shared hook](../scripts/setup.py) checks `parameterValueSet.name == EntraOAuth` on every connection read. When status is not Connected, it calls `az connector-namespace connection authenticate` with the provisioned subscription, `--timeout 300`, and `--no-access-policy`. Complete the normal browser consent flow while the CLI owns the terminal; authentication output is not captured. The helper reads the connection again and requires both EntraOAuth and Connected. It never obtains or logs legacy consent links.

## Callback registration and reruns

The helper verifies the actual Function App `defaultHostName` against the Bicep output and waits for the **system** key named `connector_extension`. It does not use a function key or the host master key. The callback is the actual HTTPS app hostname plus `/runtime/webhooks/connector?functionName={function}`. The request's notification authentication supplies the `code` query key; the secret stays in a private temporary JSON body and never appears in sample logs or command arguments.

Before any trigger or settings write, the hook completes same-collection inventory pagination and preflights every matching event's full resource identity, operation, connection, delivery mode, and owning app metadata. It pauses all listeners, registers selected callbacks, preserves unchanged sources without PUT, and retains writable recurrence and metadata fields on updates. Read-only provisioning and endpoint fields are removed from PUT bodies. Omitted owned sources become Disabled, never deleted. Only after all registrations complete does the helper enable selected listeners and set `VstsConnection` through a private JSON app-settings file.

Pending connection and source registrations receive bounded reads before setup proceeds. Failed or timed-out registrations stop setup. Continuation URLs must use the same HTTPS host and collection; malformed URLs and case-only cycles fail before writes. Runtime and actual app hostnames must be valid DNS names, not IP addresses or credential-bearing URLs.

If setup fails during registration, listeners remain paused. Resolve consent, permissions, schema, host startup, or ownership errors, then run `azd hooks run postdeploy` from this project. A late local-settings error does not roll back completed cloud registration. The helper does not persist callback keys or source selection in azd environment files; it rereads your local reviewed input file and the actual system key on every run.

## Local testing

The helper creates the ignored local settings file atomically from [local.settings.example.json](local.settings.example.json), without a local managed-identity credential. Existing local settings remain untouched by default. Refresh them with `-ForceLocalSettings` through [infra/scripts/postdeploy.ps1](infra/scripts/postdeploy.ps1), or `--force-local-settings` through [infra/scripts/postdeploy.sh](infra/scripts/postdeploy.sh). Force merges unrelated values rather than replacing the document.

Temporary request directories and generated settings use current-user-only Windows ACLs or owner-only POSIX permissions. The Windows ACL uses the current token's SID. Permission failures stop setup, temporary files are removed after success or failure, and an atomic replacement failure leaves the old local settings intact. Callback keys never enter local settings.

For local binding startup, use Azurite, sign in as the developer with connection access, install [requirements.txt](requirements.txt) in a virtual environment, and run `func start`. [host.json](host.json) uses preview bundle `[4.50.0, 5.0.0)`. The deployed subscriptions still target the **cloud** app: starting a local host does not redirect callbacks. This sample does not create public tunnels or replace callbacks with local origins. To exercise the raw handlers offline, pass any string and verify the arrival log and `None` result without parsing the payload.

For end-to-end validation, create a selected Azure DevOps event and check its log in the deployed Function App. Preview-region availability, consent, bundle startup, and actual source callback delivery need live validation; offline checks do not prove delivery.

## Cleanup

Removing an event from the input array disables its owned trigger config and cloud listener on the next hook run. It does not delete an Azure DevOps service-hook subscription. Review old connections and callback subscriptions manually, especially when migrating to the distinct `-entra` connection or replacing a Function App. The hook warns about this cleanup and never deletes unowned sources. Review the environment before using `azd down`.