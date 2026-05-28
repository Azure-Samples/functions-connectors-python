# office365AppPython

Azure Functions sample app demonstrating the **Office 365** connector triggers using Python with rich SDK types.

## Prerequisites

- **Python 3.13** or later
- **azure-functions>=2.2.0b4** (included in requirements.txt)
- **azurefunctions-extensions-connectors** (included in requirements.txt)

## Triggers included

| Function | Type | Description |
|---|---|---|
| `OnNewEmail` | `ClientReceiveMessage` | New email arrives |
| `OnFlaggedEmail` | `GraphClientReceiveMessage` | Email is flagged |
| `OnNewMentionMeEmail` | `GraphClientReceiveMessage` | Email mentions current user |
| `OnNewCalendarEvent` | `GraphCalendarEventClientReceive` | New calendar event created |
| `OnUpcomingEvent` | `GraphCalendarEventClientReceive` | Upcoming event notification |

## Rich SDK Types

This sample uses the `azurefunctions-extensions-connectors` package which provides rich type hints:

```python
import azurefunctions.extensions.connectors.office365 as office365
from typing import List

@app.connector_trigger(arg_name="emails")
def on_new_email(emails: List[office365.ClientReceiveMessage]) -> None:
    for email in emails:
        print(f"Subject: {email.subject}")
        print(f"From: {email.from_}")
```

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
office365AppPython/
├── function_app.py           # Python v2 programming model with rich types
├── requirements.txt          # Python dependencies (includes connectors SDK)
├── infra/
│   ├── main.bicep            # azd entrypoint (subscription scope)
│   ├── resources.bicep       # Storage + App Insights + Function App
│   └── main.parameters.json
├── azure.yaml
├── host.json
└── local.settings.json
```
