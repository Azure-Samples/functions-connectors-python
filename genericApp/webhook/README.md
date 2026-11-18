# Generic connector webhook trigger (Python)

The Connector Namespace calls the deployed function's callback for any connector operation configured for webhook delivery.

| Function | Binding |
| --- | --- |
| `OnGenericConnectorEvent` | `str` (raw payload) |

The handler logs only its name, not payload content. This app does not provision Azure resources.

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local), and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) for local runs.
- An existing Connector Namespace, authorized connection, and webhook trigger configs ([webhook setup guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md#webhook-delivery)).
- An existing Python Function App to deploy to (this sample does not create one), with a system-assigned identity and identity-based host storage.
- Python SDK: `azure-functions>=2.4.0` on Python 3.13+; see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

1. Publish:

   ```sh
   az login
   func azure functionapp publish <function-app-name>
   ```

2. In each trigger config, set `notificationDetails`:
   - `callbackUrl`: `https://<function-app-host>/runtime/webhooks/connector?functionName=OnGenericConnectorEvent`
   - `authentication`: `type: "QueryString"`, `name: "code"`, `value`: the host's **`connector_extension` system key** (not a function key). Keep it private.

## Local development

1. Copy `local.settings.example.json` to `local.settings.json`.
2. Start Azurite.
3. Run:

   ```sh
   python -m venv .venv
   . .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   func start --enableAuth
   ```

To receive events locally, expose the host through an HTTPS tunnel and point a trigger config's callback at it with the local `connector_extension` system key. Keep `--enableAuth`; without it Core Tools skips key checks. Restore deployed callbacks afterwards.

## Test

Generate a source event and look for `OnGenericConnectorEvent (generic API) trigger received.` in the function logs. Delivery may repeat.

## Deprovision

Remove only trigger configs you created for this sample. Never commit callback keys or `local.settings.json`.
