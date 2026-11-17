# Azure Functions connectors samples (Python)

This repository contains Python samples for the **Connector Namespace** integration with Azure Functions. Each connector folder documents its supported events, bindings, prerequisites, and setup steps. Start with the guide for the connector you want to use.

## What are Functions connectors?

Azure Functions integrates with the managed connectors platform that backs Logic Apps and Power Platform:

- **Connector triggers** — run a function when an event occurs in an external service, such as a new email, file, or Teams message.

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

- `jq` (for bash post-deploy scripts on macOS/Linux)

## Getting-started samples

Follow each connector's guide for deployment or setup. Each `polling` or `webhook` folder is an independent app; some samples use existing Azure resources rather than provisioning them with `azd up`.

The included deployment templates use Python 3.14 on Flex Consumption.

| Guide | Connector |
| --- | --- |
| [Office 365](./office365App/README.md) | [Office 365 Outlook](https://learn.microsoft.com/connectors/office365/) |
| [SharePoint](./sharepointApp/README.md) | [SharePoint Online](https://learn.microsoft.com/connectors/sharepointonline/) |
| [OneDrive](./onedriveApp/README.md) | [OneDrive for Business](https://learn.microsoft.com/connectors/onedriveforbusiness/) |
| [Teams](./teamsApp/README.md) | [Microsoft Teams](https://learn.microsoft.com/connectors/teams/) |
| [Dataverse](./dataverseApp/README.md) | [Microsoft Dataverse (Common Data Service)](https://learn.microsoft.com/connectors/commondataservice/) |
| [Azure Blob](./azureblobApp/README.md) | [Azure Blob Storage](https://learn.microsoft.com/connectors/azureblob/) |
| [Generic](./genericApp/README.md) | [Any connector](https://learn.microsoft.com/connectors/), using raw string payloads |
| [Kusto](./kustoApp/README.md) | [Azure Data Explorer](https://learn.microsoft.com/connectors/kusto/) |
| [Azure DevOps](./azureDevOpsApp/README.md) | [Azure DevOps (Entra OAuth)](https://learn.microsoft.com/connectors/visualstudioteamservices/) |
| [Planner](./plannerApp/README.md) | [Microsoft Planner](https://learn.microsoft.com/connectors/planner/) |
| [Salesforce](./salesforceApp/README.md) | [Salesforce](https://learn.microsoft.com/connectors/salesforce/) |

## More triggers and operations

See the [Operations to Azure Functions Signature Mapping](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md) for supported connector triggers and their Python signatures.

## The packages these samples use

| Package | Stable minimum | Role |
| --- | --- | --- |
| [`azure-functions`](https://pypi.org/project/azure-functions/) | `>=2.4.0` (Python 3.13+) | The Azure Functions Python SDK. |
| [`azurefunctions-extensions-connectors`](https://pypi.org/project/azurefunctions-extensions-connectors/) | `>=1.0.0` | Connector trigger bindings. |

Install requirements from the selected app's folder. Requirements select the Functions SDK for your Python version; the generic raw-payload samples do not need the connector extension.

### Python 3.12 and older supported versions

On Python 3.12 and older supported Functions runtimes, requirements select `azure-functions>=1.27.0b1`. Set `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` locally and in the deployed app. This older SDK requires a beta minimum because no stable 1.27.0 release exists. Deployment templates use Python 3.14.

## Related repos

| Repo | Purpose |
| --- | --- |
| [Azure/connectors-python-SDK](https://github.com/Azure/connectors-python-SDK) | `azure-connectors` — Python SDK for Azure Connectors. |
| [Azure/azure-functions-python-extensions](https://github.com/Azure/azure-functions-python-extensions) | `azurefunctions-extensions-connectors` — the binding extension consumed by these samples. |
