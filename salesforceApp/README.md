# Salesforce connector samples (Python)

Choose [polling](polling/README.md) or [webhook](webhook/README.md). Each folder has its own Azure Developer CLI project and infrastructure. Use a separate azd environment for each mode: a source cannot safely change delivery mode in place. Both modes expose the same functions:

| Function | Connector operation | Input type |
|---|---|---|
| `OnSalesforceNewItems` | `GetOnNewItems` | `list[salesforce.Item]` |
| `OnSalesforceUpdatedItems` | `GetOnUpdatedItems` | `list[salesforce.Item]` |

Handlers log only the function name and record count, never record fields or payloads. The Salesforce extension wraps the generated SDK `Item` model and returns a list of records. These samples demonstrate delivery, not business processing or deduplication.

## Prerequisites

- Python 3.14 for the deployed app; the dependency markers also support the older SDK branch for local Python below 3.13.
- Azure Developer CLI, Azure CLI, and a `connector-namespace` CLI extension that supports `connection authenticate --timeout 300 --no-access-policy`.
- An Azure subscription with Connector Namespace preview access in the selected region, and Flex Consumption support in the app region.
- Rights to create resources and role assignments. The developer principal parameter expects a user object ID; service-principal deployments need an explicit developer user ID.
- A Salesforce account with connector authentication access and permission to read the selected object and fields. Confirm that the Salesforce edition/account supports the API and that new/changed records can be read through the selected connector operations. Do not assume access to an object implies access to every field or record.

The namespace, Function App system-assigned identity, and developer each get a connection access policy. The app and developer get Blob Data Owner, Queue Data Contributor, and Table Data Contributor roles for host/deployment storage. Storage shared-key access and Application Insights local authentication stay off. Application Insights uses Entra authentication and Metrics Publisher grants. Python 3.14 and `FC1` come from `functionAppConfig`; there is no cloud `FUNCTIONS_WORKER_RUNTIME`. `alwaysReady` is empty.

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

Run `azd up` from the chosen mode folder after signing in to Azure. The root `postdeploy` hook runs only after code deployment. It validates azd outputs, pins every Azure command to the provisioned subscription, authenticates Salesforce if needed, then inventories the namespace and checks ownership for **both** known functions before any trigger write.

Initial cloud listeners stay disabled. Poll sources are not Bicep resources: the hook creates them only after authentication. Webhooks use the verified deployed `defaultHostName` and the `connector_extension` system key. The key goes into `notificationDetails.authentication` as QueryString authentication named `code`, never into an output, local setting, or printed command. JSON requests and cloud settings use private temporary files that the helper removes on every exit.

Source registration must report `Succeeded`; failed, canceled, or indefinitely pending sources stop the hook. The hook enables only selected listeners after readiness checks and disables deselected owned sources by changing only `state` to `Disabled`. It does not DELETE anything. Unchanged sources receive no PUT; updates preserve other writable properties and omit server-generated `provisioningState` and `pollingEndpoints`. A different app, connection, operation, or delivery mode with the same source name stops setup rather than overwriting it.

To change selected objects/events or recover after consent/registration failure, edit ignored `trigger-inputs.json` and rerun `azd hooks run postdeploy`. Source changes are not a transaction: if a later source or settings write fails, earlier writes may remain. Listeners remain in their prior state until the final settings write. Rerun after resolving the failure; do not claim a partial run succeeded.

## Local settings and privacy

The hook creates ignored `local.settings.json` atomically with Azurite host storage and developer authentication. It preserves an existing file byte-for-byte; pass `--force` to the Python helper (or `-ForceLocalSettings` to PowerShell) to replace it explicitly. No managed-identity cloud credential/client ID or callback key is copied into local settings. Run Azurite before starting a local host. Public examples start with both functions disabled and contain no resource IDs or secrets.

Both shell wrappers call `salesforceApp/scripts/setup.py` via `../../../scripts/setup.py`. The PowerShell postdeploy wrapper accepts `-Inputs <path>`; the shell wrapper forwards `--inputs <path>` and `--force`. The helper accepts `--mode polling|webhook --project <mode-folder>`. Running setup makes Azure changes; importing it does not.

Private local settings, trigger inputs, azd environments, Python caches, and staging files are excluded from Git and/or deployment. Do not enable verbose CLI output around secret-bearing requests. The authentication CLI inherits the terminal's input and output without capture and rejects noninteractive input; enter credentials only in its own browser or terminal, never in the input JSON.

Before writing callback JSON or new local settings, the helper restricts a fresh staging directory. On Windows it runs `icacls` through PowerShell, removes inherited permissions, grants the current user inheritable full control, and checks that no other principal has an allow entry. It fails before writing files if this check fails. On POSIX it uses directory mode `0700` and file mode `0600`. This is local access control, not encryption or protection against administrators. It does not change permissions or contents of an existing preserved local settings file.

Connection readback must match the configured nonempty authentication selector as well as the connector and namespace resource ID. An empty selector leaves the choice to the service. The helper retries a missing connector extension key six times before it stops without any trigger PUT. Invalid JSON, duplicate JSON keys, non-finite numbers, malformed ownership fields, and invalid or cyclic continuation URLs stop setup. Unknown writable source fields, including nested nulls and large JSON integers, stay intact on updates; null ownership or notification objects are invalid, not empty defaults.

## Validation scope

Local compilation and mocked helper checks do not prove live Salesforce authentication, field permissions, source registration, callback delivery, or regional preview support. These samples make no live validation claim. Confirm both new and updated record delivery in your connected Salesforce environment before relying on them.