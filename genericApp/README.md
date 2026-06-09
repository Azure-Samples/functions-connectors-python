# Generic Connector Triggers (Python — untyped)

Azure Functions sample demonstrating the **generic (untyped) connector trigger binding**
with `string` payloads instead of strongly-typed SDK models.

Use the generic API when you want to:

- Bind a trigger for a connector that does **not** have a first-class wrapper yet.
- Forward the payload as-is (e.g. to a queue, blob, or AI model) without deserializing.
- Keep a minimal dependency footprint.
- Work with any Azure Logic Apps connector.

> The function **name** still binds to the connector + operation on the host side. The
> generic API only changes the parameter type — it does **not** change which
> operation the function listens to.

## Triggers included

| Function | Connector | Description |
|---|---|---|
| `OnGenericOffice365NewEmail` | Office 365 | Fires on new email — raw JSON payload |
| `OnGenericAzureBlobUpdated` | Azure Blob | Fires on blob add/modify — raw JSON payload |
| `OnGenericSharepointNewFile` | SharePoint Online | Fires on new file — raw JSON payload |
| `OnGenericTeamsChannelMessage` | Teams | Fires on channel message — raw JSON payload |
| `OnGenericCustomConnectorEvent` | _any connector_ | Placeholder for custom connectors — raw JSON payload |

Each handler receives the raw JSON as a `string` via `@app.connector_trigger(arg_name="payload")`.

## When to use this vs. the typed API

| Use case | Approach |
|---|---|
| Connector with a generated SDK model (e.g. Office 365, Teams) | Use the typed payload class (see `office365App`, `teamsApp`) |
| Connector without a first-class SDK wrapper | Use `connector_trigger` with string payload (this sample) |
| Forward payload as-is to storage or downstream service | Use `connector_trigger` with string payload (this sample) |

## Prerequisites

- [Python 3.13](https://www.python.org/downloads/) or later
- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- [`connector-namespace` Azure CLI extension](https://github.com/Azure/Connectors)

  ```powershell
  # PowerShell
  irm https://aka.ms/connector-namespace-cli-install-ps | iex
  ```

  ```bash
  # Bash
  curl -fsSL https://aka.ms/connector-namespace-cli-install | sh
  ```

## Run locally

```bash
pip install -r requirements.txt
func start
```

Update `local.settings.json` with the runtime URL and token for each connection you want to trigger on.

## Deploy

```bash
azd auth login
cd genericApp
azd up
```

This sample does **not** include infrastructure or post-deploy scripts because the
connector and trigger configuration depends on which connector you want to use.
Copy the `infra/` folder from one of the other apps (e.g. `office365App`) and adjust
the connector name and trigger parameters to match your scenario.

The connector trigger requires the **Preview** Functions Extension Bundle (`Microsoft.Azure.Functions.ExtensionBundle.Preview`).
This is already configured in `host.json`.

## Project layout

```text
genericApp/
├── function_app.py           # All generic trigger functions (string payload)
├── requirements.txt          # Python dependencies
├── host.json
├── azure.yaml
└── local.settings.json
```
