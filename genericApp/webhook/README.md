# Generic connector webhook triggers (Python)

Five functions preserve the existing illustrative names. Each receives raw `str`
and logs only `<FunctionName> (generic API) trigger received.` No payload parsing,
event-content logging, or connector SDK models are used.

| Function | Example operation |
| --- | --- |
| `OnGenericOffice365NewEmail` | Office 365 `OnNewEmailV3` |
| `OnGenericAzureBlobUpdated` | Azure Blob `OnUpdatedFiles_V2` |
| `OnGenericSharepointNewFile` | SharePoint `GetOnNewFileItems` |
| `OnGenericTeamsChannelMessage` | Teams `OnNewChannelMessage` |
| `OnGenericCustomConnectorEvent` | Another supported connector operation |

These are illustrative mappings, not provisioned resources. The function name
routes its callback; it does not subscribe automatically. Choose a supported
operation, connection, and parameters in each Connector Namespace trigger config.

## Prerequisites

- Functions Core Tools v4, a supported Python runtime, Azure CLI, and Azurite for local storage.
- An existing Connector Namespace identity, authorized connection, and enabled
  Webhook trigger configs. Follow the [webhook configuration guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md#webhook-delivery).
- Requirements select `azure-functions>=2.4.0b1` on Python 3.13+, or
  `azure-functions>=1.27.0b1` for older supported versions. On Python 3.12 and older,
  set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` locally and in Azure. The local example
  includes it. No connector SDK or rich binding extension package is required.

This app has no provisioning template, `azd up`, or postdeploy hooks. Use a dedicated
connector sample to provision resources or configure existing resources manually.

## Configure and deploy

Publish to an existing Python Function App with configured host/deployment storage:

Enable its **system-assigned managed identity** and keep the namespace identity.
Set `AzureWebJobsStorage__credential=managedidentity` and the host account's
`AzureWebJobsStorage__blobServiceUri`, `AzureWebJobsStorage__queueServiceUri`, and
`AzureWebJobsStorage__tableServiceUri`. Grant the app principal
Storage Blob Data Owner, Storage Queue Data Contributor, and
Storage Table Data Contributor on the host account. For Flex deployment storage, use `SystemAssignedIdentity` and grant
Storage Blob Data Contributor on its container (covered by Blob Data Owner when
the account is shared). Do not deploy `FUNCTIONS_WORKER_RUNTIME` on Flex.

```bash
cd genericApp/webhook
func azure functionapp publish <function-app-name>
```

Local settings are not published. Keep the included Preview extension bundle and
configure dependency isolation for Python 3.12 and older.

For each namespace trigger, set `notificationDetails.callbackUrl` to:

```text
https://<actual-function-app-host>/runtime/webhooks/connector?functionName=<FunctionName>
```

Set `notificationDetails.authentication` to `type: "QueryString"`, `name: "code"`,
and `value` equal to the host's **`connector_extension` system key**, not an ordinary
function key. Do not print or commit the key. Source operation parameters remain
connector-specific; raw-string binding does not change them.

## Run locally

If missing, copy `local.settings.example.json` to `local.settings.json`, preserving
existing settings. Create and activate a virtual environment and install requirements:

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

Start Azurite separately first. Core Tools bypasses key checks locally by default;
use `--enableAuth` before exposing the host publicly. To receive real events locally, expose the host
through a secure public HTTPS tunnel and configure separate trigger callbacks using
the local function names and connector extension system key. Remote host keys do
not authenticate the local host. Restore deployed callbacks if you change them,
or use the [polling app](../polling) to avoid a public tunnel.

## Verify and clean up

Cause the configured source event and confirm a successful function invocation
with the matching receipt log. A running host alone does not prove delivery.
Logs intentionally exclude payloads. Treat delivery as at least once when adding
side effects. Never commit tokens, callback keys, or private local settings.

Disable or remove only trigger configurations created for your test. Do not delete
shared resources. Configure host Application Insights settings if telemetry is
needed; this sample adds no separate Python telemetry exporter.

For Entra telemetry, set `APPLICATIONINSIGHTS_AUTHENTICATION_STRING=Authorization=AAD`,
grant the app principal Monitoring Metrics Publisher, and set
`ConnectorNamespace__credential=managedidentity` for the worker's identity-only
section. Omit it locally for developer credentials. The .NET worker's exporter
factory has no Python equivalent here. See the
[Flex identity/storage reference](https://github.com/Azure-Samples/azure-functions-flex-consumption-samples/blob/main/IaC/bicep/main.bicep).
