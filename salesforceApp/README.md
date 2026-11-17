# Salesforce connector samples (Python)

Choose [polling](polling/README.md) or [webhook](webhook/README.md). Each folder is a standalone copyable Azure Developer CLI project, including its own setup helper, hooks, infrastructure, ignore rules and full permission/setup guide. No parent script is required. Use a separate azd environment for each mode: a source cannot safely change delivery mode in place. Both modes expose the same functions:

| Function | Connector operation | Input type |
|---|---|---|
| `OnSalesforceNewItems` | `GetOnNewItems` | `typing.List[salesforce.Item]` |
| `OnSalesforceUpdatedItems` | `GetOnUpdatedItems` | `typing.List[salesforce.Item]` |

Handlers log only the function name and record count, never record fields or payloads. The Salesforce extension wraps the generated SDK `Item` model and returns a list of records. These samples demonstrate delivery, not business processing or deduplication.

## Prerequisites

- Python 3.14 for the deployed app; Python 3.12 and newer local environments install their matching SDK through each mode's requirements.
- Azure Developer CLI 1.33.0 or newer for layered provisioning.
- Azure Developer CLI, Azure CLI, and a `connector-namespace` CLI extension that supports `connection authenticate --timeout 300 --no-access-policy`.
- An Azure subscription with Connector Namespace preview access in the selected region, and Flex Consumption support in the app region.
- Rights to create resources and role assignments. The developer principal parameter expects a user object ID; service-principal deployments need an explicit developer user ID.
- A Salesforce account with connector authentication access and permission to read the selected object and fields. Confirm that the Salesforce edition/account supports the API and that new/changed records can be read through the selected connector operations. Do not assume access to an object implies access to every field or record.

Only the Function App system-assigned identity and developer get connection access policies; the namespace identity gets no self-access policy. The app and developer get Blob Data Owner, Queue Data Contributor, and Table Data Contributor roles for host/deployment storage. Storage shared-key access and Application Insights local authentication stay off. Application Insights uses Entra authentication and Metrics Publisher grants. Python 3.14 and `FC1` come from `functionAppConfig`; there is no cloud `FUNCTIONS_WORKER_RUNTIME`. `alwaysReady` is empty. Each mode's README lists the required Azure and Salesforce permissions.

## Python dependencies

Both projects require `azurefunctions-extensions-connectors>=1.0.0`; its SDK dependency is transitive, not a direct sample requirement. Requirements select `azure-functions>=1.27.0b1` when `python_version < '3.13'` and `azure-functions>=2.4.0` when `python_version >= '3.13'`. Install the selected mode's requirements in an activated virtual environment; no manual Functions SDK bootstrap is needed. Generated cloud/local settings and public examples use `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`. Both hosts use stable `Microsoft.Azure.Functions.ExtensionBundle` range `[4.41.2, 5.0.0)`.

## Reviewed trigger inputs

Copy the selected mode's `trigger-inputs.example.json` to ignored `trigger-inputs.json`. Replace each `<REAL_SALESFORCE_OBJECT_ID>` with the **actual object type identifier**, not a record ID or display label. Delete the whole entry for an event you do not want. Do not submit the example unchanged. At least one event must remain.

Both operations have the required string wire parameter `table`, and optional strings `$filter`, `$orderby`, and `$select`. Omit optional parameters you do not need. Names keep their `$` prefix. The hook rejects unknown fields, duplicate functions/parameters, a mismatched operation, blank values, and placeholders. It never creates sources from guessed object names. If there is no local input file, the hook prompts for event selection, actual object IDs, and optional queries in a real terminal.

The connector's **Salesforce Object Type** selector resolves through `GetTables`: collection `value`, identifier `Name`, display label `DisplayName`. Obtain the real identifier from the connected Salesforce object's picker or an authorized `GetTables` response. These samples accept a reviewed identifier; they do not treat the Salesforce Swagger example text as a usable identifier. Test optional OData queries against the connected object and its field permissions before using them here.

### Contract sources

- Node Salesforce webhook sample pinned to main commit `158d7e9944caa99f12ec481f1a837320720916d6`: its `webhook-config.json` supplies the function/operation mapping, `trigger-inputs.mjs` resolves Swagger selectors and wire parameters, and `connectorNamespace.bicep` uses `parameterValueSet.name = BasicAuthentication` with empty values.
- The local Salesforce Swagger inspection confirms `table`, `$filter`, `$orderby`, `$select`, and the `GetTables` selector above. The Python SDK `TRIGGER_OPERATIONS` confirms the two operation routes and required `table` parameter.
- The Python connector extension's Salesforce `item.py` and record samples supply the typed list binding. No generator or generated SDK files change here.

The infrastructure keeps the pinned `BasicAuthentication` selector by default. `SALESFORCE_AUTHENTICATION_PARAMETER_SET` controls this selector; an empty value omits `parameterValueSet` for a service-selected default. Do not put credentials in the parameter file. Despite the pinned selector name, the hook follows the modern interactive connection authentication flow and trusts the connection's `Connected` readback, not the CLI exit alone. It skips authentication when consent already exists.

## Provision and register

Run `azd up` from the chosen mode folder after signing in to Azure. Polling provisions foundation resources, then obtains consent and validates source selection in the triggers layer hook. That hook reconciles enabled Poll configs and waits for ready receive endpoints **before** the app layer creates/configures the app and deploys code. Poll postdeploy only writes local settings. See the [polling deployment and rerun guide](polling/README.md#provision-and-deploy).

Webhook provisions foundation and app layers, deploys code with sample listeners disabled, then registers sources in postdeploy after consent and host readiness. It uses the verified deployed `defaultHostName` and `connector_extension` system key. The key goes into `notificationDetails.authentication` as QueryString authentication named `code`, never an output or local setting. See the [webhook guide](webhook/README.md#provision-and-deploy).

Both modes validate azd outputs, pin Azure requests to the provisioned subscription, and inventory/check ownership of **both** known source names before trigger writes. Both app layers read existing settings and merge sample-owned values without dropping unrelated settings. Webhook's final listener update also reads and merges existing cloud settings. JSON requests and settings use private temporary files removed on success/failure.

Selected source registration must report `Succeeded` and `Enabled`; failed, canceled, disabled or indefinitely pending sources stop setup. Only selected listeners are enabled, and only owned deselected sources change `state` to `Disabled`. The helper never deletes configs. Unchanged sources receive no PUT; updates preserve other writable properties and omit server-generated `provisioningState` and `pollingEndpoints`. A different app, connection, operation, or delivery mode with the same source name stops setup rather than overwriting it.

To change polling selection, edit ignored `trigger-inputs.json`, then rerun `azd provision triggers`, `azd provision app`, and `azd deploy --all` in order. For webhook selection, rerun `azd hooks run postdeploy`. Source/deployment/settings changes are not a transaction: earlier writes may remain after a failure, and enabled Poll configs may collect events before an app consumes them. Resolve failures and rerun in order; do not claim partial success. Avoid concurrent settings writers against the same app.

## Local settings and privacy

The hook creates ignored `local.settings.json` atomically with Azurite host storage and developer authentication. It preserves an existing file byte-for-byte; pass `--force` to the Python helper (or `-ForceLocalSettings` to PowerShell) to replace it explicitly. No managed-identity cloud credential/client ID or callback key is copied into local settings. Run Azurite before starting a local host. Public examples start with both functions disabled and contain no resource IDs or secrets.

Each mode's PowerShell and POSIX wrappers call its own `infra/scripts/setup.py`. The helper accepts `--mode polling|webhook --project <mode-folder>` and a layer `--phase triggers|app|postdeploy`. Polling reads reviewed inputs in the triggers phase, not postdeploy. Webhook's postdeploy wrapper accepts `-Inputs <path>` on PowerShell or `--inputs <path>` on POSIX. Running setup may make Azure changes; importing it does not. Copy either mode alone with its dotfiles to retain all hooks and ignore rules.

Private local settings, trigger inputs, azd environments, Python caches, and staging files are excluded from Git and/or deployment. Do not enable verbose CLI output around secret-bearing requests. The authentication CLI inherits the terminal's input and output without capture and rejects noninteractive input; enter credentials only in its own browser or terminal, never in the input JSON.

Before writing callback JSON or new local settings, the helper restricts a fresh staging directory. On Windows it runs `icacls` through PowerShell, removes inherited permissions, grants the current user inheritable full control, and checks that no other principal has an allow entry. It fails before writing files if this check fails. On POSIX it uses directory mode `0700` and file mode `0600`. This is local access control, not encryption or protection against administrators. It does not change permissions or contents of an existing preserved local settings file.

Connection readback must match the configured nonempty authentication selector as well as the connector and namespace resource ID. An empty selector leaves the choice to the service. The helper retries a missing connector extension key six times before it stops without any trigger PUT. Invalid JSON, duplicate JSON keys, non-finite numbers, malformed ownership fields, and invalid or cyclic continuation URLs stop setup. Unknown writable source fields, including nested nulls and large JSON integers, stay intact on updates; null ownership or notification objects are invalid, not empty defaults.

## Validation scope

Local compilation and mocked helper checks do not prove live Salesforce authentication, field permissions, source registration, callback delivery, or regional preview support. These samples make no live validation claim. Confirm both new and updated record delivery in your connected Salesforce environment before relying on them.