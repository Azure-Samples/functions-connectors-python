# kustoAppPython

Azure Functions sample app demonstrating the **Azure Data Explorer (Kusto)** connector triggers using Python.

## Prerequisites

- [A supported Python version](https://learn.microsoft.com/azure/azure-functions/functions-versions?tabs=isolated-process%2Cv4&pivots=programming-language-python#languages)
- `azure-functions>=2.4.0` on Python 3.13+.

On Python 3.12 and older supported versions, manually install
`azure-functions>=1.27.0b1` before sample requirements and set
`PYTHON_ISOLATE_WORKER_DEPENDENCIES=1` locally and in Azure. See the
[older Python setup](../README.md#python-312-and-older-supported-versions).

## Triggers included

- `OnKustoQueryResult`

## Run locally

```bash
pip install -r requirements.txt
func start
```

Update `local.settings.json` with your connector runtime URL and access token before starting.

## Deploy to Azure

`azd up` will provision a Flex Consumption Function App (Python 3.14), a Storage account, Application Insights, and Log Analytics, then deploy the Python code.

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

The connector trigger requires the **Preview** Functions Extension Bundle (`Microsoft.Azure.Functions.ExtensionBundle.Preview`). This is already configured in `host.json`.

## Project layout

```
kustoAppPython/
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
