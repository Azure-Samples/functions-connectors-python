# Salesforce webhook delivery

This folder is a standalone Azure Developer CLI project. Copy the whole folder, including its dotfiles and [infra](infra), to use it without the rest of the repository. All hooks use the local [setup helper](infra/scripts/setup.py); no parent script or document is required. Use a different azd environment from Poll delivery: a source cannot safely change delivery mode in place.

## Prerequisites and permissions

- Python 3.12 or a supported newer local Python, Azure Functions Core Tools v4, and Azurite for local runs. Azure runs Python 3.14 on Linux Flex Consumption (`FC1`).
- Azure Developer CLI **1.33.0 or newer**, Azure CLI, and the `connector-namespace` CLI extension with `connection authenticate --timeout 300 --no-access-policy` support. Install the extension from the Connector Namespace preview onboarding instructions for your subscription.
- PowerShell 7 on Windows, or POSIX `sh` on macOS/Linux. Hooks use `python` by default; set `PYTHON` to the desired executable if needed. No `jq` is required.
- A subscription with Connector Namespace preview access in the namespace region (default `brazilsouth`) and Flex Consumption support in the app region.
- Contributor rights to create resources, plus Role Based Access Control Administrator or User Access Administrator at the deployment scope for storage/monitoring role assignments. The caller also needs connection, access-policy and trigger-config management, Function App settings read/update, and host/system-key read permissions.
- A developer **user object ID** in the deployment tenant. A user sign-in supplies this by default; a service-principal deployer must supply the developer user ID through `AZURE_PRINCIPAL_ID`.
- A Salesforce account/edition with API and connector authentication access, and read permission for the chosen objects, fields and records. Object access alone does not grant field or record access. Review optional queries against that account before using them.

The developer and Function App system-assigned identity get connection access policies; the namespace identity gets **no** self-access policy. The developer and app get Storage Blob Data Owner, Storage Queue Data Contributor and Storage Table Data Contributor on sample storage, and Monitoring Metrics Publisher on Application Insights. Shared-key storage access and Application Insights local authentication stay off. Cloud access uses managed identity; local access uses your `az login` identity. `functionAppConfig` selects Python 3.14; there is no cloud `FUNCTIONS_WORKER_RUNTIME` setting, and `alwaysReady` is empty.

## Install and select inputs

From this folder, create and activate a virtual environment:

```powershell
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

```sh
# macOS/Linux
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

[requirements.txt](requirements.txt) installs `azure-functions>=1.27.0b1` below Python 3.13, `azure-functions>=2.4.0` on Python 3.13+, and `azurefunctions-extensions-connectors>=1.0.0`. The extension supplies its SDK dependency; do not add a direct `azure-connectors` requirement. Python 3.12 needs no manual Functions SDK bootstrap. Generated local settings, the example, and cloud settings set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`.

Copy [trigger-inputs.example.json](trigger-inputs.example.json) to ignored `trigger-inputs.json`. Replace every `<REAL_SALESFORCE_OBJECT_ID>` with an actual reviewed **object type identifier**, not a record ID or label. The Salesforce Object Type selector resolves through `GetTables`, collection `value`, ID field `Name` and display label `DisplayName`. Use the connected object picker or an authorized `GetTables` response; do not use Swagger example text as an identifier.

| Function | Operation | Binding |
|---|---|---|
| `OnSalesforceNewItems` | `GetOnNewItems` | `typing.List[salesforce.Item]` |
| `OnSalesforceUpdatedItems` | `GetOnUpdatedItems` | `typing.List[salesforce.Item]` |

Keep at least one event; remove an unwanted event's whole entry. Each operation requires string `table`, and accepts optional strings `$filter`, `$orderby`, and `$select`. Preserve `$` prefixes and omit unused parameters. The helper validates the input contract (fields, duplicate functions/parameters, operation mapping, blank values and placeholders), not live Salesforce permissions. If no file exists, it prompts for selected events, actual IDs and optional queries in an interactive terminal.

## Provision and deploy

Sign in and create a distinct environment from this folder:

```sh
az login
azd auth login
azd env new salesforce-webhook-demo
azd env set AZURE_LOCATION eastus2
azd env set CONNECTOR_NAMESPACE_LOCATION brazilsouth
azd up
```

Choose regions enabled for your subscription. `APPLICATION_INSIGHTS_LOCATION` can override telemetry placement. `SALESFORCE_AUTHENTICATION_PARAMETER_SET` defaults to the pinned Node sample's `BasicAuthentication`; an empty value omits `parameterValueSet` for a service-selected default. Do not put credentials in Bicep parameters. Despite that selector's name, the helper uses interactive connection authentication and verifies `Connected` after consent. It skips authentication if consent already exists.

[azure.yaml](azure.yaml) packages code, provisions **base**, then provisions **app**, deploys code, and runs the local postdeploy hook:

1. Base creates storage/deployment container, plan, monitoring, namespace, connection and developer grants; no trigger config exists yet.
2. App preprovision inventories the app and distinguishes a missing app from a failed read. [app.bicep](infra/app.bicep) reads existing app settings and [app-settings.bicep](infra/app-settings.bicep) merges sample-owned settings without dropping unrelated values. Both sample listeners start disabled. The app identity receives connection/storage/monitoring access.
3. After code deployment, the hook validates connection ID, connector, authentication selector and `Connected`, then validates inputs and inventories all known sources before any trigger write.
4. It checks the deployed `defaultHostName` against the app output and reads only `systemKeys.connector_extension`, with bounded retries. The HTTPS callback uses `/runtime/webhooks/connector?functionName=<function>` and QueryString authentication named `code`. The key stays in memory/private request JSON, never outputs or local settings.
5. Once registration reports `Succeeded` and `Enabled`, the helper reads existing cloud settings, merges selected listener flags, and writes through a private file. Only then does it write local settings.

Both functions use `connection="ConnectorNamespace"`, with no Poll delivery or trigger-config-name argument. Handlers receive `typing.List[salesforce.Item]` and log only names/counts. The underlying Salesforce operations use GET; webhook describes Connector Namespace-to-Function delivery, not Salesforce native outbound messages.

## Reruns, local runs, and privacy

After changing ignored `trigger-inputs.json` or resolving a consent/registration failure, run `azd hooks run postdeploy`. To use another reviewed input path, run `./infra/scripts/postdeploy.ps1 -Inputs <path>` on Windows or `sh ./infra/scripts/postdeploy.sh --inputs <path>` on POSIX. A full `azd up` rerun reprovisions the app, briefly disables its sample listeners, then reenables only the selected listeners after successful registration.

The helper checks **both** known source names before any trigger PUT. Foreign app, connection, operation or delivery mode, duplicate IDs, malformed ownership, null notification objects, unsafe/cyclic continuation URLs, missing keys, mismatched hostnames and failed registration stop setup. It changes only `state` to disable **owned deselected** configs, never deletes configs, leaves unchanged sources untouched, and preserves unknown writable fields except server-generated `provisioningState` and `pollingEndpoints`.

Generated ignored local settings use Azurite and developer authentication, with `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, no managed-identity cloud credential and no callback key. Existing files stay byte-for-byte unchanged unless you pass `-ForceLocalSettings` to PowerShell or `--force` to POSIX. Refresh an old preserved local file after changing selection. The public [example](local.settings.example.json) disables both listeners.

For host indexing, start Azurite separately, keep `az login` signed in as the developer, and run `func start`. **Cloud callbacks do not redirect to localhost.** Local webhook delivery needs a separately reviewed HTTPS tunnel and a local connector extension system key; this sample configures only cloud delivery. Never substitute the default/function key for the connector system key or log record payloads.

Git/deployment ignores are local to this folder and exclude settings, reviewed inputs, azd state, caches and staging files. New local settings and callback/settings requests use private temporary directories: POSIX `0700` and file `0600`; Windows removes inherited/other allow grants and checks the current-user-only ACL. Staging files are removed on all exits. These controls are not encryption or protection against administrators, and do not alter a preserved existing file. Enter credentials only in the authentication browser/terminal and avoid verbose CLI tracing around secret-bearing requests.

Source and settings writes are not a transaction. Earlier writes may remain if a later operation fails. Listener settings keep their prior values until the final settings merge. Resolve the failure and rerun; do not treat a partial run as success. Settings merges do not serialize concurrent external changes, so avoid simultaneous deployments/settings writers against the same app.

## Validation limits

[host.json](host.json) uses stable `Microsoft.Azure.Functions.ExtensionBundle`, range `[4.41.2, 5.0.0)`. Local compilation and mocked checks do not prove OAuth, regional preview support, Salesforce field/record access, host readiness or real callback delivery. Verify new and updated record delivery in the connected Salesforce environment before relying on this sample.