# Azure Blob connector triggers (Python)

Choose a standalone [polling app](./polling/README.md) or [webhook app](./webhook/README.md). Both run `OnAzureBlobUpdatedFile` for the Azure Blob connector's [`OnUpdatedFiles_V2`](https://learn.microsoft.com/connectors/azureblob/#when-a-blob-is-added-or-modified-(properties-only)-(v2)) operation when a blob is added or modified. This is the **Connector Namespace** integration, not the native Storage BlobTrigger.

Each folder includes its own infrastructure, dependencies, hooks, and local settings example. Run `azd up` from the chosen folder. Use different azd environment names if you deploy both, so they do not overwrite resources.

| Delivery | How it receives events |
| --- | --- |
| Polling | The host receives and acknowledges events through the namespace endpoint using Microsoft Entra credentials; no public callback is needed. |
| Webhook | The namespace sends events to the Functions connector callback, authenticated with the connector extension system key. |

## Python requirements

| Python | Minimum Functions SDK | Required app setting |
| --- | --- | --- |
| 3.13+ | `azure-functions>=2.4.0` | None |
| 3.12 and older supported versions | `azure-functions>=1.27.0b1`, installed manually | `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` |

Requirements install the SDK only on Python 3.13+; on older versions, install it before the sample requirements. Both apps require `azurefunctions-extensions-connectors>=1.0.0`. Deployment uses Python 3.14.

> [!CAUTION]
> The handlers log blob names, paths, sizes, and modification times. Use test data, restrict log access, and run `azd down --purge` from the app folder when finished.

See the [Azure Blob connector reference](https://learn.microsoft.com/connectors/azureblob/).