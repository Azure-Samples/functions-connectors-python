# azureblobAppPython

Azure Functions sample app demonstrating the **Azure Blob** connector triggers using Python.

## Prerequisites

- **Python 3.13** or later
- **azure-functions>=2.2.0b4** (included in requirements.txt)

## Triggers included

- `OnAzureBlobUpdatedFile`

## Run locally

```bash
pip install -r requirements.txt
func start
```

Update `local.settings.json` with your connector runtime URL and access token before starting.

## Deploy to Azure

`azd up` will provision a Linux Consumption Function App (Python 3.13), a Storage account, Application Insights,
and Log Analytics, then deploy the Python code.

```bash
azd auth login
azd up
```

At the end of provisioning, configure the connector runtime URL and token on the Function App:

```bash
azd env set CONNECTOR_RUNTIME_URL '<your-connector-runtime-url>'
azd env set CONNECTOR_TOKEN '<your-token>'
azd provision
```

The connector trigger requires the **Preview** Functions Extension Bundle (`Microsoft.Azure.Functions.ExtensionBundle.Preview`).
This is already configured in `host.json`.

## Project layout

```
azureblobAppPython/
├── function_app.py           # Python v2 programming model entry point
├── requirements.txt          # Python dependencies
├── infra/
│   ├── main.bicep            # azd entrypoint (subscription scope)
│   ├── resources.bicep       # Storage + App Insights + Function App
│   └── main.parameters.json
├── azure.yaml
├── host.json
└── local.settings.json
```
