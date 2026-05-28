# Azure Functions connectors samples (Python)

This repository contains Python samples that show how to use the new **Connector Namespace** integration with Azure Functions. Each sample lives in its own folder so you can clone, deploy, and explore independently with a single `azd up`.

> [!NOTE]
> Connectors in Azure Functions are in **public preview**. The Connector Namespace is currently available in **West Central US (`westcentralus`)**; your function app can be deployed in any region that supports the chosen hosting plan. See the [overview](https://learn.microsoft.com/azure/azure-functions/) for details.

## Prerequisites

- **Python 3.13** or later
- **azure-functions>=2.2.0b4**
- [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) for deployment
- An Azure subscription
- A configured connector connection for the connector you want to trigger on

> The connector trigger requires the **Preview** Functions Extension Bundle (`Microsoft.Azure.Functions.ExtensionBundle.Preview`, version `[4.42.*, 5.0.0)`) — already pre-configured in every sample's `host.json`.

## What are Functions connectors?

Azure Functions integrates with the managed connectors platform that backs Logic Apps and Power Platform, giving your functions:

- **Connector triggers** — a function runs when an event occurs in an external service (new email in Office 365, file added to SharePoint or OneDrive, message posted to Microsoft Teams, and many more). The runtime exposes a `connector_trigger` binding that receives webhook callbacks from the Connector Namespace.
- **Connector SDK actions** — function code calls connector operations through strongly-typed clients or through dynamic payload models for any connector.

The connector platform handles webhook registration, OAuth flows, token refresh, and retry — you focus on the business logic.

## Getting-started samples

Seven self-contained Azure Functions apps, each deployable with `azd up`:

| App | Connector | Triggers demonstrated |
|---|---|---|
| [`azureblobApp/`](./azureblobApp) | Azure Blob | `OnAzureBlobUpdatedFile` |
| [`kustoApp/`](./kustoApp) | Azure Data Explorer (Kusto) | `OnKustoQueryResult` |
| [`office365App/`](./office365App) | Office 365 Outlook | `OnNewEmail`, `OnFlaggedEmail`, `OnNewMentionMeEmail`, `OnNewCalendarEvent`, `OnUpcomingEvent` |
| [`onedriveApp/`](./onedriveApp) | OneDrive for Business | `OnOneDriveNewFile`, `OnOneDriveUpdatedFile` |
| [`sharepointApp/`](./sharepointApp) | SharePoint Online | `OnSharepointNewFile`, `OnSharepointUpdatedFile` |
| [`teamsApp/`](./teamsApp) | Microsoft Teams | `OnNewChannelMessage`, `OnNewChannelMessageMentioningMe`, `OnGroupMembershipAdd`, `OnGroupMembershipRemoval` |
| [`genericApp/`](./genericApp) | _any connector_ — uses the generic `connector_trigger` API | Azure Blob, Office 365, SharePoint, Teams + a custom-type example |

## The packages these samples use

| Package | Role |
|---|---|
| [`azure-functions`](https://pypi.org/project/azure-functions/) | The Functions Python worker. Provides `@app.connector_trigger` decorator and the broader bindings surface. |
| [`azurefunctions-extensions-connectors`](https://pypi.org/project/azurefunctions-extensions-connectors/) | Rich SDK types for Office 365 connector triggers (`ClientReceiveMessage`, `GraphClientReceiveMessage`, `GraphCalendarEventClientReceive`). Used by `office365App`. |

## What each sample shows

### `azureblobApp` — Azure Blob

A single function `OnAzureBlobUpdatedFile` that fires when blobs in a watched Azure Blob container are updated. The payload contains `Name`, `Path`, `Size`, `LastModified` fields.

### `kustoApp` — Azure Data Explorer (Kusto)

`OnKustoQueryResult` runs whenever the configured Kusto query produces a non-empty result. Each row is accessible from the parsed JSON payload.

### `office365App` — Office 365 Outlook (with rich SDK types)

Five Outlook triggers using the `azurefunctions-extensions-connectors` package for rich type hints:

| Function | Type | Fires when… |
|---|---|---|
| `OnNewEmail` | `List[ClientReceiveMessage]` | A new email lands in the watched mailbox / folder |
| `OnFlaggedEmail` | `List[GraphClientReceiveMessage]` | An email is flagged (follow-up) |
| `OnNewMentionMeEmail` | `List[GraphClientReceiveMessage]` | A new email @-mentions the connection identity |
| `OnNewCalendarEvent` | `List[GraphCalendarEventClientReceive]` | A new calendar event is created |
| `OnUpcomingEvent` | `List[GraphCalendarEventClientReceive]` | A calendar event is about to start |

### `onedriveApp` — OneDrive for Business

`OnOneDriveNewFile` and `OnOneDriveUpdatedFile`. Both parse the payload to extract file metadata (`Name`, `Path`, `Size`, `LastModified`).

### `sharepointApp` — SharePoint Online

`OnSharepointNewFile` and `OnSharepointUpdatedFile`. Both parse the payload to extract file metadata.

### `teamsApp` — Microsoft Teams

Four Teams triggers:

| Function | Fires when… |
|---|---|
| `OnNewChannelMessage` | A new channel message is posted |
| `OnNewChannelMessageMentioningMe` | A channel message @-mentions the connection identity |
| `OnGroupMembershipAdd` | A user is added to a Teams group |
| `OnGroupMembershipRemoval` | A user is removed from a Teams group |

### `genericApp` — generic `connector_trigger` API

Demonstrates the generic API that works for any Azure Logic Apps connector — including connectors that do not have a first-class wrapper yet. The payload is received as a JSON string and parsed manually.

| Function | Connector |
|---|---|
| `OnGenericAzureBlobUpdated` | Azure Blob |
| `OnGenericOffice365NewEmail` | Office 365 |
| `OnGenericSharepointNewFile` | SharePoint Online |
| `OnGenericTeamsChannelMessage` | Teams |
| `OnGenericCustomConnectorEvent` | _any custom connector_ |

## How a trigger function looks

### With rich SDK types (Office 365)

```python
import azure.functions as func
import azurefunctions.extensions.connectors.office365 as office365
from typing import List

app = func.FunctionApp()

@app.function_name(name="OnNewEmail")
@app.connector_trigger(arg_name="emails")
def on_new_email(emails: List[office365.ClientReceiveMessage]) -> None:
    for email in emails:
        logging.info(f"Subject: '{email.subject}'.")
        logging.info(f"From: '{email.from_}'.")
```

### Generic: string payload (any connector)

```python
import azure.functions as func
import json
import logging

app = func.FunctionApp()

@app.function_name(name="OnAzureBlobUpdatedFile")
@app.connector_trigger(arg_name="payload")
def on_azure_blob_updated_file(payload: str) -> None:
    data = json.loads(payload)
    files = data.get("body", {}).get("value", [])
    
    for file in files:
        logging.info(f"Name: '{file.get('Name')}'.")
        logging.info(f"Path: '{file.get('Path')}'.")
```

## Run a sample locally

```bash
cd <connectorAppPython>
pip install -r requirements.txt
func start
```

Update `local.settings.json` with the runtime URL and access token for your connector before starting. The keys differ per connector (e.g. `Office365Connection` / `OFFICE365_TOKEN`, `TeamsConnection` / `TEAMS_TOKEN`).

## Deploy a sample to Azure

```bash
cd <connectorAppPython>
azd auth login
azd up
```

`azd up` provisions a resource group containing:

- Azure Storage account (Function App backing store).
- Linux Consumption Function App (Python 3.13) with system-assigned managed identity.
- Application Insights + Log Analytics workspace.

It then runs the `prepackage` hook (`pip install -r requirements.txt`) and deploys the Python code.

After provisioning, configure the connector runtime URL and token:

```bash
azd env set CONNECTOR_RUNTIME_URL '<your-connector-runtime-url>'
azd env set CONNECTOR_TOKEN '<your-token>'
azd provision   # re-runs the Bicep to push the new app settings
```

## Repository layout

```
functions-connectors-python/
├── README.md
├── azureblobAppPython/
├── kustoAppPython/
├── office365AppPython/
├── onedriveAppPython/
├── sharepointAppPython/
├── teamsAppPython/
└── genericAppPython/
```

Each app folder is self-contained:

```
<connectorAppPython>/
├── function_app.py             # Python v2 programming model entry point
├── requirements.txt            # Python dependencies
├── infra/
│   ├── main.bicep              # subscription-scope: creates RG, delegates to resources.bicep
│   ├── resources.bicep         # Storage + App Insights + Function App
│   └── main.parameters.json    # ${AZURE_ENV_NAME}, ${AZURE_LOCATION}, ${CONNECTOR_RUNTIME_URL=}, ${CONNECTOR_TOKEN=}
├── azure.yaml                  # azd service definition + prepackage hook
├── host.json                   # Preview extension bundle + logging
├── local.settings.json         # placeholders for runtime URL + token
└── README.md
```

## Related repos

| Repo | Purpose |
|---|---|
| [Azure/connectors-python-SDK](https://github.com/Azure/connectors-python-SDK) | `azure-connectors` — generated Python SDK for Azure Connectors. |
| [Azure/azure-functions-python-extensions](https://github.com/Azure/azure-functions-python-extensions) | `azurefunctions-extensions-connectors` — the binding extension consumed by these samples. |