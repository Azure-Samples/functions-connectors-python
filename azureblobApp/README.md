# Azure Blob connector triggers (Python)

Use the [polling app](./polling/README.md) if the Functions host should pull events from the Connector Namespace without a public endpoint. Use the [webhook app](./webhook/README.md) if the namespace should call the deployed function. Both apps run `OnAzureBlobUpdatedFile` for the [`OnUpdatedFiles_V2`](https://learn.microsoft.com/connectors/azureblob/#when-a-blob-is-added-or-modified-(properties-only)-(v2)) operation when a blob is added or modified. These samples use the Connector Namespace, not the native Storage blob trigger.

See the [Azure Blob connector reference](https://learn.microsoft.com/connectors/azureblob/).
