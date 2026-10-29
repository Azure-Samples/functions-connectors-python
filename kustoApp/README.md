# kustoAppPython

Azure Functions sample app demonstrating the **Azure Data Explorer (Kusto)** connector triggers using Python.

## Prerequisites

- [A supported Python version](https://learn.microsoft.com/azure/azure-functions/functions-versions?tabs=isolated-process%2Cv4&pivots=programming-language-python#languages)
- `azure-functions>=2.3.0b1` (the documented minimum; dependency files are unchanged by this update)

## Triggers included

- `OnKustoQueryResult`

## Raw trigger payload

Keep `payload: str` with `@app.connector_trigger(arg_name="payload")` and parse the query-result
JSON with `json.loads(payload)`. The target `azurefunctions-extensions-connectors>=1.0.0b4`
extension has no supported Kusto trigger type binding. A generated action SDK client or model
does not add binding support, and installing the extension does not change this raw contract.

Kusto is an extra Python event sample, beyond the 15 dedicated and five generic events shared
with the .NET samples. This documentation update does not edit handlers or dependency files.

## Run locally

```bash
pip install -r requirements.txt
func start
```

Update `local.settings.json` with your connector runtime URL and access token before starting.

## Deploy to Azure

`azd up` will provision a Flex Consumption Function App (Python 3.14), a Storage account, Application Insights,
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
