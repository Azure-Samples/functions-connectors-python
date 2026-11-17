# Salesforce Poll delivery

This folder is a standalone Azure Developer CLI project. Copy the whole folder, including its dotfiles and [infra](infra), to use it without the rest of the repository. All hooks use the local [setup helper](infra/scripts/setup.py); no parent script or document is required. Use a different azd environment from webhook delivery: a source cannot safely change delivery mode in place.

## Prerequisites and permissions

- Python 3.12 or a supported newer local Python, Azure Functions Core Tools v4, and Azurite for local runs. Azure runs Python 3.14 on Linux Flex Consumption (`FC1`).
- Azure Developer CLI **1.33.0 or newer**, Azure CLI, and the `connector-namespace` CLI extension with `connection authenticate --timeout 300 --no-access-policy` support. Install the extension from the Connector Namespace preview onboarding instructions for your subscription.
- PowerShell 7 on Windows, or a POSIX `sh` on macOS/Linux. Hooks call `python` by default; set `PYTHON` to the desired executable if it has another name. Neither platform needs `jq`.
- An Azure subscription with Connector Namespace preview access in the namespace region (default `brazilsouth`) and Flex Consumption support in the app region.
- Contributor rights to create resources, plus Role Based Access Control Administrator or User Access Administrator at the deployment scope to create the storage and monitoring role assignments. The caller also needs permission to manage Connector Namespace connections, access policies and trigger configs, and read/update Function App settings.
- A developer **user object ID** in the deployment tenant. User sign-in supplies this by default; a service-principal deployer must explicitly supply the developer user ID with `AZURE_PRINCIPAL_ID`.
- A Salesforce account/edition with API and connector authentication access, and read access to each selected object, field and record. Object access alone does not grant field or record access. Review optional queries against that account before using them.

The developer and Function App system-assigned identity get connection access policies; the namespace identity does **not** get a self-access policy. The developer and app get Storage Blob Data Owner, Storage Queue Data Contributor and Storage Table Data Contributor on sample storage, plus Monitoring Metrics Publisher on Application Insights. Shared-key storage access and Application Insights local authentication stay off. Cloud settings use managed identity; local settings use your `az login` identity. `functionAppConfig` selects Python 3.14, not a cloud `FUNCTIONS_WORKER_RUNTIME` setting. `alwaysReady` is empty.

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

[requirements.txt](requirements.txt) installs `azure-functions>=1.27.0b1` on Python below 3.13 and `azure-functions>=2.4.0` on Python 3.13+. It also installs `azurefunctions-extensions-connectors>=1.0.0`, which supplies its SDK dependency; do not install a separate direct `azure-connectors` requirement. No manual SDK bootstrap is needed on Python 3.12. Generated local settings, the example, and cloud settings all set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`.

Copy [trigger-inputs.example.json](trigger-inputs.example.json) to ignored `trigger-inputs.json`. Replace every `<REAL_SALESFORCE_OBJECT_ID>` with a reviewed **object type identifier**, not a record ID or display label. The connector's Salesforce Object Type selector uses `GetTables`, collection `value`, ID field `Name`, and label `DisplayName`. Obtain identifiers from the connected object picker or an authorized `GetTables` response; Swagger example text is not an identifier.

| Function | Operation | Binding |
|---|---|---|
| `OnSalesforceNewItems` | `GetOnNewItems` | `typing.List[salesforce.Item]` |
| `OnSalesforceUpdatedItems` | `GetOnUpdatedItems` | `typing.List[salesforce.Item]` |

Keep at least one entry; delete an unwanted event's whole entry. Both operations require string `table` and accept optional strings `$filter`, `$orderby`, and `$select`. Keep the `$` prefix and omit unused parameters. The hook rejects unknown fields, duplicates, mismatched operations, blank values, placeholders, and invalid JSON. It validates the input contract, not live object/field permissions. With no file it asks for event selection, actual IDs, and optional queries in an interactive terminal.

## Provision and deploy

Sign in and create a distinct environment from this folder:

```sh
az login
azd auth login
azd env new salesforce-poll-demo
azd env set AZURE_LOCATION eastus2
azd env set CONNECTOR_NAMESPACE_LOCATION brazilsouth
azd up
```

Choose regions enabled for your subscription. `APPLICATION_INSIGHTS_LOCATION` optionally overrides the telemetry region. `SALESFORCE_AUTHENTICATION_PARAMETER_SET` defaults to the pinned Node sample's `BasicAuthentication`; an empty value omits `parameterValueSet` for a service-selected default. Do not put credentials in parameter files. Despite the selector's name, setup uses the interactive authentication flow and trusts `Connected` readback, not the CLI exit alone.

[azure.yaml](azure.yaml) runs these ordered stages:

1. Package the code, then provision **base**: resource group, storage/deployment container, plan, monitoring, namespace, Salesforce connection, and developer permissions. It does not create the Function App or Poll configs.
2. Before **triggers**, the local hook checks the connection's resource ID, connector and authentication selector; obtains OAuth consent if needed; and confirms `Connected`. It then validates the selected sources and checks ownership of **both** known source names before any trigger PUT.
3. The hook creates/reconciles selected **enabled** `deliveryMode: Poll` configs using REST. It waits for `Succeeded` and `Enabled`, then reads `pollingEndpoints.receiveUri`. The triggers Bicep layer records only the resulting nonsecret settings; REST ownership checks, not Bicep, control trigger writes.
4. Before **app**, inventory detects whether the app already exists. The app layer reads existing app settings and merges sample-owned host, identity, endpoint, trigger-name and listener settings through [app-settings.bicep](infra/app-settings.bicep). It preserves unrelated settings. The app identity gets connection/storage/monitoring access.
5. Deploy the code. The local postdeploy hook writes local settings only; Poll registration does not wait until after code deployment.

Both functions use `connection="ConnectorNamespace"`, explicit `DeliveryMode.POLL`, and their `%OnSalesforce...TriggerConfigName%` setting. They log only function names and counts. The endpoint validator requires HTTPS and the matching receive path, preserves the gateway prefix (including `/api/connectorGateways/...`), and strips only a trailing `/api` before `/triggerConfigs`. All selected sources must agree on the gateway. No callback key is used.

## Reruns, local runs, and privacy

To change selection, edit ignored `trigger-inputs.json`, then run `azd provision triggers`, `azd provision app`, and `azd deploy --all` in that order. After fixing a failed stage, rerun it and the later stages. `azd hooks run postdeploy` only refreshes local settings; it does not change sources. To bypass terminal prompts, prepare the reviewed input file before provisioning.

The helper refuses foreign apps, connections, operations, delivery modes, duplicate IDs and malformed ownership. It disables only **owned deselected** configs by changing `state` to `Disabled`; it never deletes configs. It leaves unchanged sources untouched and preserves unknown writable fields on updates, excluding server-generated `provisioningState` and `pollingEndpoints`. Failed/canceled registration, unsafe/cyclic continuation URLs, and mismatched gateways stop setup.

The generated ignored local settings use Azurite, the endpoint and trigger names, selected listener flags, and `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, without the cloud managed-identity credential. Existing local settings stay byte-for-byte unchanged unless you request replacement: use `./infra/scripts/postdeploy.ps1 -ForceLocalSettings` on Windows or `sh ./infra/scripts/postdeploy.sh --force` on POSIX. If selection changed, refresh or edit an old preserved file before local testing. The public [example](local.settings.example.json) starts with both listeners disabled.

Start Azurite separately, keep `az login` signed in as the developer with connection access, and run `func start` from this folder. Stop the cloud app first if testing the same Poll configs locally; the two hosts would compete for messages. Do not log record payloads or customer fields.

Private settings, reviewed inputs, staging files, azd state and Python caches have local Git/deployment ignore rules. Request files and new local settings use a private staging directory (POSIX `0700`/files `0600`; Windows removes inherited/other allow grants and verifies the current-user-only ACL). Files are removed on success/failure. This is access control, not encryption or protection from administrators. Authentication uses its own browser/terminal; never put credentials in inputs or enable verbose CLI tracing around secret-bearing requests.

Source writes and deployment are not one transaction. If a later stage fails, earlier enabled configs may remain and collect events before an app consumes them; an existing app keeps its previous settings until the app layer runs. Resolve the cause and rerun in order. Settings merges preserve unrelated values but cannot prevent concurrent external writers from racing; do not run two deployments against the same app at once.

## Validation limits

[host.json](host.json) uses the stable `Microsoft.Azure.Functions.ExtensionBundle` with range `[4.41.2, 5.0.0)`. Local compilation and mocked checks do not prove Salesforce OAuth, regional preview support, field permissions, registration, retention during partial provisioning, or real delivery. Verify both new and changed records in your connected Salesforce environment before relying on this sample.