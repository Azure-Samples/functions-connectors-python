# Generic Connector Triggers (Python — untyped)

Azure Functions sample demonstrating the **generic (untyped) connector trigger binding**
with raw `str` payloads instead of typed trigger bindings. All five handlers intentionally
remain raw, including Office 365, SharePoint, and Teams where typed alternatives exist.

Use the generic API when you want to:

- Bind a trigger for an operation that does **not** have a supported trigger type binding.
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

Each handler receives the raw JSON as a `str` via `@app.connector_trigger(arg_name="payload")`.
Use `json.loads(payload)` when inspecting fields; do not annotate these generic handlers
with connector model types. A generated action SDK model alone does not establish type-binding support.

## When to use this vs. the typed API

| Use case | Approach |
|---|---|
| Operation with a supported trigger type binding (e.g. the Outlook or Teams examples) | Use the extension binding type in the dedicated app |
| Operation without a supported trigger type binding | Use `connector_trigger` with a raw `str` payload |
| Forward payload as-is, or demonstrate the generic API even when a typed alternative exists | Keep `connector_trigger` with a raw `str` payload (this sample) |

## Prerequisites

- `azure-functions>=2.3.0b1`. The typed examples in the dedicated apps target
  `azurefunctions-extensions-connectors>=1.0.0b4`; this generic sample does not need a typed
  binding and stays raw even if that package is installed. This documentation update does not edit dependency files.
- [A supported Python version](https://learn.microsoft.com/azure/azure-functions/functions-versions?tabs=isolated-process%2Cv4&pivots=programming-language-python#languages)
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
the connector name and trigger parameters to match your scenario. The sample infrastructure
deploys a Flex Consumption Function App with Python 3.14; keep that runtime version when copying it.

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
