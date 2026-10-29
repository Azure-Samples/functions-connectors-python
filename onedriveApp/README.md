# OneDrive for Business Triggers (Python)

Azure Functions sample app demonstrating **OneDrive for Business** connector triggers using the
`azurefunctions-extensions-connectors` package with the Functions connector trigger extension.

| Function | Connector operation | Description |
| --- | --- | --- |
| `OnOneDriveNewFile` | [`OnNewFilesV2`](https://learn.microsoft.com/en-us/connectors/onedriveforbusiness/#when-a-file-is-created) | Fires when a new file is created in OneDrive |
| `OnOneDriveUpdatedFile` | [`OnUpdatedFilesV2`](https://learn.microsoft.com/en-us/connectors/onedriveforbusiness/#when-a-file-is-modified-(properties-only)) | Fires when a file is modified in OneDrive |

## Prerequisites

- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Azure CLI (`az`)](https://learn.microsoft.com/cli/azure/install-azure-cli) ≥ 2.75.0
- [A supported Python version](https://learn.microsoft.com/azure/azure-functions/functions-versions?tabs=isolated-process%2Cv4&pivots=programming-language-python#languages)
- [`connector-namespace` Azure CLI extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli) — install with:

  ```bash
  # Bash
  curl -fsSL https://aka.ms/connector-namespace-cli-install | sh
  ```

  or

  ```pwsh
  # PowerShell
  irm https://aka.ms/connector-namespace-cli-install-ps | iex
  ```

## Deploy to Azure

```bash
cd onedriveApp
azd auth login
az login
azd up
```

### Resources provisioned

| Resource | Purpose |
| --- | --- |
| **Resource Group** | Contains all resources |
| **Flex Consumption Function App** (Python 3.14) | Hosts the connector trigger functions |
| **App Service Plan** (FC1) | Flex Consumption plan |
| **User-Assigned Managed Identity** | Identity for the function app |
| **Storage Account** | Deployment artifacts and function runtime state |
| **Log Analytics Workspace** | Backing store for Application Insights |
| **Application Insights** | Telemetry and logging |
| **Connector Namespace** | Hosts the OneDrive connection and trigger configs |
| **OneDrive for Business Connection** (OAuth) | Authenticates to OneDrive — requires interactive consent during post-deploy |

After provisioning, a post-deploy hook authorizes the OneDrive connection and creates trigger configs. To re-run:

```bash
azd hooks run postdeploy
```

## Target trigger type bindings

Use `azure-functions>=2.3.0b1` and `azurefunctions-extensions-connectors>=1.0.0b4`.
Both `OnOneDriveNewFile` (`OnNewFilesV2`) and `OnOneDriveUpdatedFile` (`OnUpdatedFilesV2`)
target `list[onedriveforbusiness.BlobMetadata]`, imported from the binding extension:

```python
import azure.functions as func
import azurefunctions.extensions.connectors.onedriveforbusiness as onedriveforbusiness

app = func.FunctionApp()

@app.function_name(name="OnOneDriveNewFile")
@app.connector_trigger(arg_name="files")
def on_onedrive_new_file(files: list[onedriveforbusiness.BlobMetadata]) -> None:
  for file in files:
    print(file.name, file.path, file.size, file.last_modified)
```

Use the same parameter type for the updated-file handler. Metadata uses model attributes,
not raw JSON dictionary keys. A split-on callback still returns a one-item list.
This documentation-only migration leaves the handler and dependency files unchanged.

## Verify

After `azd up`, open the [Connector Namespaces portal](https://connectors.azure.com/) to verify:

- One **Connection** (OneDrive for Business) with status **Connected**
- Trigger configs in **Enabled** state

Create or modify a file in OneDrive to fire the trigger. Tail logs with:

```bash
az functionapp log tail -g <resourceGroupName> -n <functionAppName>
```

## More

- [Operations to Functions Signature Mapping](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md)
- [OneDrive for Business connector reference](https://learn.microsoft.com/en-us/connectors/onedriveforbusiness/)
