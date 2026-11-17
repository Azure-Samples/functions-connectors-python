# Generic connector webhook trigger (Python)

`OnGenericConnectorEvent` receives raw `str` payloads from any supported connector operation configured for webhook delivery. The handler logs only the function name.

This folder is a standalone Function App. Run all commands from this folder; no parent or sibling files are required. It does not provision Azure resources.

## Prerequisites

- A supported Python version, [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local), Azure CLI, and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) for local runs.
- An existing Connector Namespace, authorized connection, and enabled webhook trigger configs. See the [webhook setup guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md#webhook-delivery).
- An existing Python Function App with host and deployment storage for Azure deployment.
- `azure-functions>=2.4.0` for Python 3.13+. For Python 3.12 and older supported versions, install `azure-functions>=1.27.0b1` before installing `requirements.txt`, which does not install the older SDK.

## Configure and deploy

Enable the app's system-assigned identity. Configure identity-based host storage with `AzureWebJobsStorage__credential=managedidentity` and the account's `__blobServiceUri`, `__queueServiceUri`, and `__tableServiceUri` settings. Grant Storage Blob Data Owner, Storage Queue Data Contributor, and Storage Table Data Contributor on the host account. For Flex deployment storage, use `SystemAssignedIdentity` and grant Storage Blob Data Contributor on the deployment container. Do not set `FUNCTIONS_WORKER_RUNTIME` on Flex.

```bash
az login
func azure functionapp publish <function-app-name>
```

For each trigger config, set `notificationDetails.callbackUrl` to `https://<function-app-host>/runtime/webhooks/connector?functionName=OnGenericConnectorEvent`. Set `notificationDetails.authentication` to `type: "QueryString"`, `name: "code"`, and `value` to the host's **`connector_extension` system key**, not an ordinary function key. Keep the key private.

Keep the included Preview extension bundle in the deployed host configuration. Python 3.12 and older require `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` in Azure and local settings.

For Microsoft Entra authenticated telemetry, configure Application Insights, grant the app identity Monitoring Metrics Publisher, and set `APPLICATIONINSIGHTS_AUTHENTICATION_STRING=Authorization=AAD` and `ConnectorNamespace__credential=managedidentity`. Omit the latter locally to use developer credentials.

## Local development

- Copy `local.settings.example.json` to `local.settings.json` if absent.
- Start Azurite separately, then run:

```bash
python -m venv .venv
# Activate .venv for your shell.
python -m pip install -r requirements.txt
func start --enableAuth
```

- To receive local events, expose the host through a secure public HTTPS tunnel and configure callbacks using `OnGenericConnectorEvent` and the local `connector_extension` system key.
- Core Tools bypasses key checks by default; enable authentication before exposing the host.
- Restore deployed callbacks if you change them.

## Verify and clean up

Generate each configured source event and check for a successful invocation and matching receipt log. Delivery may repeat. Remove only trigger configs created for this sample; do not delete shared resources or commit callback keys or local settings.
