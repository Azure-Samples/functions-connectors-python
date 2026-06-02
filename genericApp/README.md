# genericAppPython

Azure Functions sample demonstrating the **generic connector trigger API** using Python.

Use the generic API when you want to:

- Bind a trigger for a connector that does **not** have a first-class wrapper yet.
- Define your own item shape (custom or partial types).
- Work with any Azure Logic Apps connector.

## Prerequisites

- **Python 3.13** or later
- **azure-functions>=2.2.0b4** (included in requirements.txt)

## Triggers included

| Function | Connector | Description |
|---|---|---|
| `OnGenericAzureBlobUpdated` | Azure Blob | Logs Name, Path, LastModified |
| `OnGenericOffice365NewEmail` | Office 365 | Logs Subject, From |
| `OnGenericSharepointNewFile` | SharePoint Online | Logs Name, Path |
| `OnGenericTeamsChannelMessage` | Teams | Logs MessageId |
| `OnGenericCustomConnectorEvent` | _any custom connector_ | Logs Id, Name |

Each handler receives the payload as a JSON string, which is parsed to extract `body.value[]` items.

## Run locally

```bash
pip install -r requirements.txt
func start
```

Update `local.settings.json` with the runtime URL and token for each connection you want to trigger on.

## Deploy to Azure

`azd up` will provision a Flex Consumption Function App (Python 3.13), a Storage account, Application Insights,
and Log Analytics, then deploy the Python code.

```bash
azd auth login
azd up
azd env set CONNECTOR_RUNTIME_URL '<your-connector-runtime-url>'
azd env set CONNECTOR_TOKEN '<your-token>'
azd provision
```

The connector trigger requires the **Preview** Functions Extension Bundle (`Microsoft.Azure.Functions.ExtensionBundle.Preview`).
This is already configured in `host.json`.

## Project layout

```
genericAppPython/
├── function_app.py           # Python v2 programming model (all triggers)
├── requirements.txt          # Python dependencies
├── infra/
│   ├── main.bicep            # azd entrypoint (subscription scope)
│   ├── resources.bicep       # Storage + App Insights + Function App
│   └── main.parameters.json
├── azure.yaml
├── host.json
└── local.settings.json
```
