# Azure Functions connectors samples (Python)

[![Sample CI](https://github.com/Azure-Samples/functions-connectors-python/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Azure-Samples/functions-connectors-python/actions/workflows/ci.yml)

Run Python Azure Functions when events occur in Teams, Outlook, Salesforce, and other services. Events arrive through a [Connector Namespace](https://connectors.azure.com/) using managed connectors.

## Deploy to Azure

### Prerequisites

- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Azure CLI (`az`)](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75.0+
- A [supported Python version](https://learn.microsoft.com/azure/azure-functions/functions-versions?tabs=isolated-process%2Cv4&pivots=programming-language-python#languages)
- The [`connector-namespace` Azure CLI extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli):

  ```bash
  # Bash
  curl -fsSL https://aka.ms/connector-namespace-cli-install | sh
  ```

  ```pwsh
  # PowerShell
  irm https://aka.ms/connector-namespace-cli-install-ps | iex
  ```

Each sample lists any additional requirements.

### Choose a sample

Most connectors have standalone `polling` and `webhook` apps. Follow the selected app's deployment steps and run `azd up` from its folder to provision and deploy. Rerun `azd up` for changes or retries. Templates deploy Python 3.14 on Flex Consumption.

The Generic samples use existing resources instead of `azd`; follow their setup instructions.

| Guide | Connector |
| --- | --- |
| [Office 365](./office365App/README.md) | [Office 365 Outlook](https://learn.microsoft.com/connectors/office365/) |
| [SharePoint](./sharepointApp/README.md) | [SharePoint Online](https://learn.microsoft.com/connectors/sharepointonline/) |
| [OneDrive](./onedriveApp/README.md) | [OneDrive for Business](https://learn.microsoft.com/connectors/onedriveforbusiness/) |
| [Teams](./teamsApp/README.md) | [Microsoft Teams](https://learn.microsoft.com/connectors/teams/) |
| [Dataverse](./dataverseApp/README.md) | [Microsoft Dataverse (Common Data Service)](https://learn.microsoft.com/connectors/commondataservice/) |
| [Azure Blob](./azureblobApp/README.md) | [Azure Blob Storage](https://learn.microsoft.com/connectors/azureblob/) |
| [Generic](./genericApp/README.md) | [Any connector](https://learn.microsoft.com/connectors/), using raw string payloads |
| [Kusto (handler scaffold)](./kustoApp/README.md) | [Azure Data Explorer](https://learn.microsoft.com/connectors/kusto/) |
| [Azure DevOps](./azureDevOpsApp/README.md) | [Azure DevOps (Entra OAuth)](https://learn.microsoft.com/connectors/visualstudioteamservices/) |
| [Planner](./plannerApp/README.md) | [Microsoft Planner](https://learn.microsoft.com/connectors/planner/) |
| [Salesforce](./salesforceApp/README.md) | [Salesforce](https://learn.microsoft.com/connectors/salesforce/) |

## Local development

Install [Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite). Follow the selected app's local development steps for dependencies, local settings, and webhook tunnels where needed.

## Test

Follow the selected app's test steps to generate source events and confirm function invocations in the logs.

See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute and [CHANGELOG.md](CHANGELOG.md) for notable changes.

## Deprovision

For `azd` apps, run from the app's folder:

```bash
azd down --purge
```

Follow the app's additional cleanup instructions for source subscriptions or manually created resources.

## More triggers

See [Connector trigger payloads for Azure Functions](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md) for all supported connector triggers and their Python signatures.

## Packages

| Package | Minimum | Role |
| --- | --- | --- |
| [`azure-functions`](https://pypi.org/project/azure-functions/) | `2.4.0` (Python 3.13+) | Azure Functions Python SDK |
| [`azurefunctions-extensions-connectors`](https://pypi.org/project/azurefunctions-extensions-connectors/) | `1.0.0` | Connector trigger bindings (not needed by the generic raw-payload samples) |

### Python 3.12 and older supported versions

Install `azure-functions>=1.27.0b1` before the sample requirements and set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` locally and in the deployed app.

## Related repos

| Repo | Purpose |
| --- | --- |
| [Azure/connectors-python-SDK](https://github.com/Azure/connectors-python-SDK) | `azure-connectors` — Python SDK for Azure Connectors. |
| [Azure/azure-functions-python-extensions](https://github.com/Azure/azure-functions-python-extensions) | `azurefunctions-extensions-connectors` — the binding extension consumed by these samples. |
