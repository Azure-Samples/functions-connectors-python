# SharePoint Online Triggers (Python)

Azure Functions sample app demonstrating **SharePoint Online** connector triggers using the
`azurefunctions-extensions-connectors` package with the Functions connector trigger extension.

| Function | Connector operation | Description |
| --- | --- | --- |
| `OnSharepointNewFile` | [`GetOnNewFileItems`](https://learn.microsoft.com/en-us/connectors/sharepointonline/#when-a-file-is-created-(properties-only)) | Fires when a new file is created in a SharePoint library |
| `OnSharepointUpdatedFile` | [`GetOnUpdatedFileItems`](https://learn.microsoft.com/en-us/connectors/sharepointonline/#when-a-file-is-created-or-modified-(properties-only)) | Fires when a file is modified in a SharePoint library |

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

Before running `azd up`, set the SharePoint site URL:

```bash
azd env set SHAREPOINT_SITE_URL "https://contoso.sharepoint.com/sites/mysite"
azd env set SHAREPOINT_LIBRARY_NAME "Documents"  # optional, defaults to "Documents"
```

Then deploy:

```bash
cd sharepointApp
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
| **Connector Namespace** | Hosts the SharePoint connection and trigger configs |
| **SharePoint Online Connection** (OAuth) | Authenticates to SharePoint — requires interactive consent during post-deploy |

After provisioning, a post-deploy hook authorizes the SharePoint connection and creates trigger configs. To re-run:

```bash
azd hooks run postdeploy
```

## Target trigger type bindings

Use `azure-functions>=2.3.0b1` and `azurefunctions-extensions-connectors>=1.0.0b4`.
Both `OnSharepointNewFile` (`GetOnNewFileItems`) and `OnSharepointUpdatedFile`
(`GetOnUpdatedFileItems`) target `list[sharepointonline.Item]`:

```python
import azure.functions as func
import azurefunctions.extensions.connectors.sharepointonline as sharepointonline

app = func.FunctionApp()

@app.function_name(name="OnSharepointNewFile")
@app.connector_trigger(arg_name="items")
def on_sharepoint_new_file(items: list[sharepointonline.Item]) -> None:
  for item in items:
    properties = item.dynamic_properties or {}
    print(properties.get("{Name}"), properties.get("{Path}"))
    print(properties.get("{FilenameWithExtension}"), properties.get("Modified"))
```

Use the same parameter type for the updated-file handler. `dynamic_properties` retains
the exact wire keys, including braces and case: `{Name}`, `{Path}`,
`{FilenameWithExtension}`, `Modified`, `ID`, and any library-specific columns that arrive.
Do not replace them with `Name`, `Path`, `LastModified`, or guessed fixed attributes.
A split-on callback still returns a one-item list. This documentation-only migration
leaves the handler and dependency files unchanged.

## Verify

After `azd up`, open the [Connector Namespaces portal](https://connectors.azure.com/) to verify:

- One **Connection** (SharePoint Online) with status **Connected**
- Trigger configs in **Enabled** state

Create or modify a file in the configured SharePoint library to fire the trigger. Tail logs with:

```bash
az functionapp log tail -g <resourceGroupName> -n <functionAppName>
```

## More

- [Operations to Functions Signature Mapping](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md)
- [SharePoint Online connector reference](https://learn.microsoft.com/en-us/connectors/sharepointonline/)
