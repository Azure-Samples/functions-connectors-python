# Generic connector polling trigger (Python)

`OnGenericConnectorEvent` receives a raw `str` payload from an existing Poll trigger config and logs only the trigger name. Poll delivery does not require a public callback.

This folder is a standalone Function App. Run all commands from this folder; no parent or sibling files are required. It does not provision Azure resources.

## Prerequisites

- A supported Python version, [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local), Azure CLI, and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) for local runs.
- An existing Connector Namespace, authorized connection, and enabled Poll trigger config. Grant both the namespace identity and receiving app/developer connection access. See the [Poll setup guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md#poll-delivery).
- An existing Python Function App with host and deployment storage for Azure deployment.
- `azure-functions>=2.4.0b1` for Python 3.13+ or `azure-functions>=1.27.0b1` for older supported versions. The requirements file selects the SDK family.

## Configure and deploy

Set these Function App settings before publishing:

| Setting | Value |
| --- | --- |
| `GenericTriggerConfigName` | Existing enabled Poll trigger config name. |
| `ConnectorNamespace__pollingEndpoint` | Base endpoint derived from the service's `pollingEndpoints.receiveUri`. |
| `ConnectorNamespace__credential` | `managedidentity` for the deployed app. |

Enable the app's system-assigned identity and grant it connection access. Configure identity-based host storage with `AzureWebJobsStorage__credential=managedidentity` and the account's `__blobServiceUri`, `__queueServiceUri`, and `__tableServiceUri` settings. Grant Storage Blob Data Owner, Storage Queue Data Contributor, and Storage Table Data Contributor on the host account. For Flex deployment storage, use `SystemAssignedIdentity` and grant Storage Blob Data Contributor on the deployment container. Do not set `FUNCTIONS_WORKER_RUNTIME` on Flex.

```bash
az login
func azure functionapp publish <function-app-name>
```

Keep the included Preview extension bundle in the deployed host configuration. Python 3.12 and older require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` in Azure and local settings.

## Local development

Copy `local.settings.example.json` to `local.settings.json` if absent, then set the trigger name and polling endpoint. Remove `/triggerconfigs/<name>/receive` and the query from the service receive URI; retain any `/api/connectorGateways/<id>` prefix, or strip a final `/api` from the base. Omit deployed managed-identity credentials locally.

Start Azurite separately, then run:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
az login
func start
```

Use the developer account granted connection access. Stop the deployed app or use separate trigger configs to avoid competing listeners.

## Verify and clean up

Generate a source event and check for a successful invocation and `OnGenericConnectorEvent (generic API) trigger received.` Delivery may repeat. Remove only trigger configs created for this sample; do not delete shared resources or commit private settings.
