# Generic connector polling trigger (Python)

The Functions host pulls events from an existing Poll trigger config on the Connector Namespace. No public endpoint is required.

| Function | Binding |
| --- | --- |
| `OnGenericConnectorEvent` | `str` (raw payload) |

The handler logs only its name, not payload content. This app does not provision Azure resources.

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local), and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) for local runs.
- An existing Connector Namespace, authorized connection, and enabled Poll trigger config ([Poll setup guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md#poll-delivery)), with connection access granted to the Function App identity and to you for local runs.
- An existing Python Function App to deploy to (this sample does not create one), with a system-assigned identity and identity-based host storage.
- Python SDK: `azure-functions>=2.4.0` on Python 3.13+; see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

1. Set these Function App settings:

   | Setting | Value |
   | --- | --- |
   | `GenericTriggerConfigName` | Poll trigger config name. |
   | `ConnectorNamespace__pollingEndpoint` | Base of the config's `pollingEndpoints.receiveUri` (see below). |
   | `ConnectorNamespace__credential` | `managedidentity` |

2. Publish:

   ```sh
   az login
   func azure functionapp publish <function-app-name>
   ```

For the polling endpoint, remove `/triggerconfigs/<name>/receive` and the query string from the receive URI; keep any `/api/connectorGateways/<id>` prefix, otherwise strip a trailing `/api`.

## Local development

1. Copy `local.settings.example.json` to `local.settings.json` and set `GenericTriggerConfigName` and `ConnectorNamespace__pollingEndpoint` (omit `ConnectorNamespace__credential` to use your `az login` identity).
2. Start Azurite.
3. Run:

   ```sh
   python -m venv .venv
   . .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   az login
   func start
   ```

Stop the deployed app or use a separate trigger config; both hosts would compete for the same events.

## Test

Generate a source event and look for `OnGenericConnectorEvent (generic API) trigger received.` in the function logs. Delivery may repeat.

## Deprovision

Remove only trigger configs you created for this sample. Never commit `local.settings.json`.
