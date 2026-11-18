# Azure Data Explorer (Kusto) query-result handler (Python)

This scaffold expects query-result notifications through a Connector Namespace webhook. It does not include a Kusto trigger configuration, and end-to-end Kusto delivery has not been validated.

| Function | Binding |
| --- | --- |
| `OnKustoQueryResult` | `str` (expects JSON with rows under `body.value`) |

> [!CAUTION]
> The handler logs every query-result row in full, which may include sensitive data. Use test data and restrict access to logs.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd).
- A compatible Connector Namespace webhook source, configured separately ([webhook setup guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md#webhook-delivery)).
- For local runs: [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).
- Python SDK: `azure-functions>=2.4.0` on Python 3.13+; see [Python 3.12 and older supported versions](../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```sh
azd auth login
azd env new kusto
azd up
```

`azd up` deploys the Function App but does not configure an event source. Rerun it for changes or retries.

For a compatible source, set the trigger config's `notificationDetails`:

- `callbackUrl`: `https://<function-app-host>/runtime/webhooks/connector?functionName=OnKustoQueryResult`
- `authentication`: `type: "QueryString"`, `name: "code"`, `value`: the host's **`connector_extension` system key** (not a function key). Keep it private.

## Local development

1. Start Azurite.
2. Run:

   ```sh
   python -m venv .venv
   . .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   func start --enableAuth
   ```

To receive events locally, expose the host through an HTTPS tunnel and point a trigger config's callback at it with the local `connector_extension` system key. Keep `--enableAuth`; without it Core Tools skips key checks.

## Test

Send a test notification with rows under `body.value` through your configured source. Check the function logs for `OnKustoQueryResult trigger received.` and the batch row count.

## Deprovision

```sh
azd down --purge
```

Remove only trigger configs you created for this sample. Never commit callback keys.
