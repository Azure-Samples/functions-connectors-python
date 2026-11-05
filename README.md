# Azure Functions connectors samples (Python)

This repository contains Python samples for the **Connector Namespace** integration with Azure Functions. Each connector folder documents its supported events, bindings, prerequisites, and setup steps. Start with the guide for the connector you want to use.

## What are Functions connectors?

Azure Functions integrates with the managed connectors platform that backs Logic Apps and Power Platform, giving your functions:

- **Connector triggers** — a function runs when an event occurs in an external service (new email in Office 365, file added to SharePoint or OneDrive, message posted to Microsoft Teams, and many more). The runtime exposes a `connector_trigger` binding that receives webhook callbacks from the Connector Namespace.
- **Connector SDK actions** — function code calls connector operations through strongly-typed clients or through dynamic payload models for any connector.

The connector platform handles webhook registration, OAuth flows, token refresh, and retry.

> [!NOTE]
> Connectors in Azure Functions are in **public preview**.

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

Follow each connector's guide for deployment or setup. When a guide offers separate polling and webhook apps, choose a delivery mode and work from that app's folder. Some samples use existing resources rather than provisioning them with `azd up`.

The included deployment templates use Python 3.14 on Flex Consumption.

| Guide | Connector |
|---|---|
| [Azure Blob](./azureblobApp/README.md) | Azure Blob Storage |
| [Dataverse](./dataverseApp/README.md) | Microsoft Dataverse (Common Data Service) |
| [Kusto](./kustoApp/README.md) | Azure Data Explorer |
| [Office 365](./office365App/README.md) | Office 365 Outlook |
| [OneDrive](./onedriveApp/README.md) | OneDrive for Business |
| [SharePoint](./sharepointApp/README.md) | SharePoint Online |
| [Teams](./teamsApp/README.md) | Microsoft Teams |
| [Generic](./genericApp/README.md) | Any connector, using raw string payloads |

## The packages these samples use

| Package | Role |
|---|---|
| [`azure-functions`](https://pypi.org/project/azure-functions/) | The Functions Python SDK. Provides `@app.connector_trigger` and the broader bindings surface. |
| [`azurefunctions-extensions-connectors`](https://pypi.org/project/azurefunctions-extensions-connectors/) | Supported connector trigger rich SDK-type bindings backed by `azure-connectors` models. |


Install the requirements from the selected app's folder. Each app specifies the package versions and Python version markers it needs; raw-payload samples may not need the rich-binding extension.


## Related repos

| Repo | Purpose |
|---|---|
| [Azure/connectors-python-SDK](https://github.com/Azure/connectors-python-SDK) | `azure-connectors` — Python SDK for Azure Connectors. |
| [Azure/azure-functions-python-extensions](https://github.com/Azure/azure-functions-python-extensions) | `azurefunctions-extensions-connectors` — the binding extension consumed by these samples. |