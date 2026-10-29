# teamsAppPython

Azure Functions sample app demonstrating the **Microsoft Teams** connector triggers using Python.

## Prerequisites

- [A supported Python version](https://learn.microsoft.com/azure/azure-functions/functions-versions?tabs=isolated-process%2Cv4&pivots=programming-language-python#languages)
- `azure-functions>=2.3.0b1` for the documented trigger binding migration
- `azurefunctions-extensions-connectors>=1.0.0b4` for the supported type bindings

## Triggers included

- `OnNewChannelMessage`
- `OnNewChannelMessageMentioningMe`
- `OnGroupMembershipAdd`
- `OnGroupMembershipRemoval`

## Target trigger type bindings

`OnNewChannelMessage` and `OnNewChannelMessageMentioningMe` target
`list[teams.ChatMessage]`. `body` and `from_` remain dictionaries; nested sender
data also uses dictionary keys, not object attributes.

```python
import azure.functions as func
import azurefunctions.extensions.connectors.teams as teams

app = func.FunctionApp()

@app.function_name(name="OnNewChannelMessage")
@app.connector_trigger(arg_name="messages")
def on_new_channel_message(messages: list[teams.ChatMessage]) -> None:
	for message in messages:
		body = message.body or {}
		sender = message.from_ or {}
		user = sender.get("user") or {}
		print(body.get("content"), user.get("displayName"))

@app.function_name(name="OnGroupMembershipAdd")
@app.connector_trigger(arg_name="members")
def on_group_membership_add(members: list[teams.OnGroupMemberChangeResponse]) -> None:
	for member in members:
		print(member.get("id"))
```

`OnGroupMembershipRemoval` uses the same membership annotation. Membership items are
dictionaries (the SDK item contract is a dictionary alias), not fixed member objects;
only read keys present in the callback. A split-on callback still returns a one-item list.
This documentation-only migration leaves the handler and dependency files unchanged.

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
teamsAppPython/
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
