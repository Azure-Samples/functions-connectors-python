# Azure Blob connector triggers (Python)

Choose a standalone [polling app](./polling/README.md) or
[webhook app](./webhook/README.md). Both run `OnAzureBlobUpdatedFile` for the
Azure Blob connector's `OnUpdatedFiles_V2` operation when a blob is added or modified.
This is the **Connector Namespace** integration, not the native Storage BlobTrigger.

Both apps use the same raw `str` payload, metadata parser, and handler. The Python
connector binding extension has no supported Azure Blob SDK model binding.
Polling adds only `delivery_mode=func.DeliveryMode.POLL` and
`trigger_config_name="%OnAzureBlobUpdatedFileTriggerConfigName%"` to the decorator.
Both use `connection="ConnectorNamespace"`.

Both Blob connections use the namespace's system-assigned managed identity, not
OAuth consent. Each namespace gets Storage Blob Data Reader on its monitored
container; the developer retains source-account upload access. This source RBAC
is separate from the Function App's host-storage roles and delivery authentication.
The hooks wait for Connected or Ready before completing setup and reject Error or
timeout. Both deployments export `connectorNamespacePrincipalId`.

Each folder includes its own infrastructure, dependencies, hooks, and local
settings example. Run `azd up` from the chosen folder. Use different azd environment
names if you deploy both, so they do not overwrite resources.

| Delivery | How it receives events |
| --- | --- |
| Polling | The host receives and acknowledges events through the namespace endpoint using Microsoft Entra credentials; no public callback is needed. |
| Webhook | The namespace sends events to the Functions connector callback, authenticated with the connector extension system key. |

## Python requirements

| Python | Minimum Functions SDK | Required app setting |
| --- | --- | --- |
| 3.13+ | `azure-functions>=2.4.0b1` | None |
| 3.12 and older supported versions | `azure-functions>=1.27.0b1` | `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` |

Both requirements files select the SDK through Python-version markers and retain
`azurefunctions-extensions-connectors>=1.0.0b4`. Deployment uses Python 3.14;
the templates and local examples include worker isolation for older runtimes.

> [!CAUTION]
> The handlers log blob names, paths, sizes, and modification times. Use test data,
> restrict log access, and run `azd down --purge` from the app folder when finished.

See the [Azure Blob connector reference](https://learn.microsoft.com/connectors/azureblob/).