# Generic connector polling trigger (Python)

`OnGenericConnectorEvent` accepts a raw `str` payload from any supported connector
operation configured for Poll delivery. It logs only
`OnGenericConnectorEvent (generic API) trigger received.` No public callback or
tunnel is required; the function deliberately does not parse or log payload data.

## Prerequisites

- Functions Core Tools v4, a supported Python runtime, Azure CLI, and Azurite for local storage.
- An existing authorized Connector Namespace connection and enabled Poll trigger
  config. Grant both the namespace identity and receiving developer/app identity
  connection access. See the [Poll setup guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md#poll-delivery).
- Requirements select `azure-functions>=2.4.0b1` on Python 3.13+, or
  `azure-functions>=1.27.0b1` on older supported versions. Python 3.12 and older
  require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`, included in the local example;
  set it in the deployed app too. No connector SDK package is needed.

This app has no provisioning template, `azd up`, or postdeploy hook. Use one of the
dedicated connector samples to provision resources, or create them separately.

## Configure and deploy

Use an existing Python Function App with host and deployment storage. Set these
deployed app settings before publishing:

| Setting | Value |
| --- | --- |
| `GenericTriggerConfigName` | Existing enabled Poll trigger config name |
| `ConnectorNamespace__pollingEndpoint` | Base derived from the service's `pollingEndpoints.receiveUri` |
| `ConnectorNamespace__credential` | `managedidentity` |

Enable the app's system-assigned identity and grant it connection access. `ConnectorNamespace` is a
setting prefix, **not** the name of the source connector connection.

For host storage, set `AzureWebJobsStorage__credential=managedidentity` and
`AzureWebJobsStorage__blobServiceUri`, `AzureWebJobsStorage__queueServiceUri`, and
`AzureWebJobsStorage__tableServiceUri` to the host account's endpoints.
Grant the app principal Storage Blob Data Owner, Storage Queue Data Contributor,
and Storage Table Data Contributor on that account. For Flex deployment storage, use
`SystemAssignedIdentity` authentication and grant Storage Blob Data Contributor
on the deployment container; Blob Data Owner covers it when the account is shared.
Keep the namespace's system-assigned identity. Do not deploy
`FUNCTIONS_WORKER_RUNTIME` on Flex; select Python through the app runtime config.

From the repository root:

```bash
cd genericApp/polling
az login
func azure functionapp publish <function-app-name>
```

Local settings are not published. Keep the included Preview extension bundle in
the deployed host configuration. Set Python 3.12 dependency isolation when applicable.

## Run locally

If absent, copy `local.settings.example.json` to `local.settings.json`. Preserve any
existing settings and fill in the endpoint and trigger config name. Derive the
endpoint from the service URI without guessing the host or losing its gateway path:

| Receive URI | Endpoint setting |
| --- | --- |
| `https://<host>/api/triggerconfigs/<name>/receive?...` | `https://<host>` |
| `https://<host>/api/connectorGateways/<id>/triggerconfigs/<name>/receive?...` | `https://<host>/api/connectorGateways/<id>` |

Remove the trigger path and query; strip a trailing `/api` only when it is the base
path. Omit deployed managed-identity credentials locally and sign in with the
developer granted connection access:

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
python -m pip install -r requirements.txt
az login
func start
```

Start Azurite separately first. Stop the deployed app while listening locally, or
use separate trigger configs to avoid competing listeners. `UseDevelopmentStorage=true`
is local only. Never commit tokens or private local settings.

## Verify

Cause an event for the operation behind your Poll config, such as a test blob
added or modified through `OnUpdatedFiles_V2`. Verify a **successful function
invocation** and the trigger-name log, not just a running admin host. Delivery may
repeat; the sample neither deduplicates nor exposes Poll `MessageId` metadata.

The host can use `APPLICATIONINSIGHTS_CONNECTION_STRING` for telemetry when
configured. This sample adds no separate Python telemetry exporter. Clean up only
sample-owned configs; do not delete shared Connector Namespace resources.

For Entra telemetry, set `APPLICATIONINSIGHTS_AUTHENTICATION_STRING=Authorization=AAD`
and grant the app principal Monitoring Metrics Publisher on Application Insights.
There is no separate Python worker exporter or .NET `AzureComponentFactory` setup.
See the [Flex identity/storage reference](https://github.com/Azure-Samples/azure-functions-flex-consumption-samples/blob/main/IaC/bicep/main.bicep).
