# Microsoft Dataverse Trigger + Action (Python)

Azure Functions sample app demonstrating the **Microsoft Dataverse** (Common Data Service)
connector using the `azurefunctions-extensions-connectors` connector trigger extension for
the trigger, plus a managed-identity HTTP function that **calls** a connector action.

| Function | Type | Connector operation | Description |
| --- | --- | --- | --- |
| `OnDataverseRowChanged` | Trigger | [`GetOnNewItems_V2`](https://learn.microsoft.com/en-us/connectors/commondataservice/#when-a-row-is-added-(admin-only)-[deprecated]) | Fires when a **new row is added** to the configured Dataverse table |
| `ListDataverseRows` | Action (HTTP) | [GetItems_V2](https://learn.microsoft.com/en-us/connectors/commondataservice/#list-rows-(legacy)-[deprecated]) (via `azure-connectors` SDK) | On-demand endpoint that **calls** the connector to list rows from the table |

> **Trigger scope & known issue:** this sample uses the **new-row** trigger `GetOnNewItems_V2`
> (*"When a row is created"*), validated end-to-end over Connector Namespace. The broader
> `SubscribeWebhookTrigger` (*"added, modified or deleted"*) is **not usable via Connector Namespace
> yet** — creating its trigger config currently fails with **HTTP 500** (`Regex.Match` null-reference).
> The team is adding support; until then, use `GetOnNewItems_V2`.

> **Why `commondataservice` (not `commondataserviceforapps`):** the successor connector ships only to
> Power Automate and **isn't available for Logic Apps / Connector Namespaces yet**. The legacy
> [`commondataservice`](https://learn.microsoft.com/en-us/connectors/commondataservice/) stays
> supported there until it is. Don't switch until the replacement is available in that environment.

## What you configure

Point the sample at any environment / table without editing code — all via `azd env set`:

| Input | azd env var | Default | Notes |
| --- | --- | --- | --- |
| **Environment (name)** | `DATAVERSE_ENVIRONMENT_NAME` | _(empty)_ | Friendly name, e.g. `Contoso (default)`. The org URL is auto-resolved from this name during post-deploy. |
| **Environment (URL)** | `DATAVERSE_ENVIRONMENT_URL` | _(empty)_ | Explicit org URL, e.g. `https://org.crm.dynamics.com`. Takes precedence when set. Passed to the trigger as the `dataset` value. |
| **Table name** | `DATAVERSE_TABLE_NAME` | `accounts` | The entity set (plural logical) name, e.g. `accounts`, `contacts`. |

Provide **either** `DATAVERSE_ENVIRONMENT_NAME` (recommended — the URL is discovered for you)
**or** `DATAVERSE_ENVIRONMENT_URL`.

## Prerequisites

- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Azure CLI (`az`)](https://learn.microsoft.com/cli/azure/install-azure-cli) ≥ 2.75.0
- [A supported Python version](https://learn.microsoft.com/azure/azure-functions/functions-versions?tabs=isolated-process%2Cv4&pivots=programming-language-python#languages)
- A Microsoft Dataverse environment and an account with access to the target table
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

## Deploy to Azure

```bash
cd dataverseApp
azd auth login
az login

# Configure the trigger (name is auto-resolved to the org URL; or set the URL directly).
azd env set DATAVERSE_ENVIRONMENT_NAME "Contoso (default)"
azd env set DATAVERSE_TABLE_NAME       "accounts"

azd up
```

### Resources provisioned

| Resource | Purpose |
| --- | --- |
| **Resource Group** | Contains all resources |
| **Flex Consumption Function App** (Python 3.14) | Hosts the trigger + action functions |
| **App Service Plan** (FC1) | Flex Consumption plan |
| **User-Assigned Managed Identity** | Identity for the function app |
| **Storage Account** | Deployment artifacts and function runtime state |
| **Log Analytics Workspace** | Backing store for Application Insights |
| **Application Insights** | Telemetry and logging |
| **Connector Namespace** | Hosts the Dataverse connection and trigger config |
| **Dataverse Connection** (OAuth) | Connects to your Dataverse environment |

The connection uses **OAuth**. After provisioning, a post-deploy hook opens a browser for
interactive consent, then creates the trigger config pointing at the function's connector webhook
URL. To re-run trigger setup (e.g. after changing the table):

```bash
azd env set DATAVERSE_TABLE_NAME "contacts"
azd provision          # re-applies app settings + access policies
azd hooks run postdeploy
```

## Target trigger type binding

Use `azure-functions>=2.3.0b1` and `azurefunctions-extensions-connectors>=1.0.0b4`.
The existing `GetOnNewItems_V2` registration targets `list[commondataservice.Item]`:

```python
import azure.functions as func
import azurefunctions.extensions.connectors.commondataservice as commondataservice

app = func.FunctionApp()

@app.function_name(name="OnDataverseRowChanged")
@app.connector_trigger(arg_name="items")
def on_dataverse_row_changed(items: list[commondataservice.Item]) -> None:
  for item in items:
    properties = item.dynamic_properties or {}
    print(properties.get("accountid"), properties.get("name"))
```

`dynamic_properties` holds the row's exact column keys. `accountid` and `name` are
account-table examples, not fixed attributes or required fields for every table.
Keep column names and case as supplied by the connector. A split-on callback still
returns a one-item list.

## Call the connector action (List rows)

Besides *receiving* the trigger, `ListDataverseRows` *calls* the Dataverse **List rows** action
against the connection's runtime URL using the typed
[`azure-connectors`](https://pypi.org/project/azure-connectors/) SDK:

```python
async with credential:
  async with CommondataserviceClient(runtime_url, credential=credential) as client:
    rows = [
      row async for row in client.list_items(
        dataset=environment_url, table=table, top=5
      )
    ]
```

Use `azure-connectors>=0.6.0b1`. The SDK builds the List rows request and returns an async pager.
Consume every page while both the credential and client contexts remain open. Pass the Dataverse
org URL as `dataset`, the **table** (entity set plural name), and an integer `top`.
The client accepts an **explicit credential per environment** directly (not
`DefaultAzureCredential`): in Azure the function app's **system-assigned managed identity** (no client
id), and locally your `az login` identity. The environment is detected via the `IDENTITY_ENDPOINT`
variable that Azure injects when managed identity is available.

> **Notes on `IDENTITY_ENDPOINT`:** App Service, Functions, and Container Apps inject this variable to
> expose the local MI token endpoint, so its presence is a reliable "running in Azure with MI" signal
> (it survives Flex Consumption, unlike `WEBSITE_INSTANCE_ID`) — see
> [managed identity docs](https://learn.microsoft.com/azure/app-service/overview-managed-identity?tabs=portal%2Chttp#connect-to-azure-services-in-app-code).
> It's host-specific (VM/VMSS use IMDS, AKS uses `AZURE_FEDERATED_TOKEN_FILE`), so don't treat it as a
> general "am I in Azure?" check. The local-vs-cloud branch is a dev convenience — **production apps
> should pick one credential** and use it unconditionally.

For the token exchange to succeed, that identity must have an **access policy** on the connection.
The infrastructure grants:

| Access policy | Principal | Why |
| --- | --- | --- |
| `functionapp-msi` | Function app system-assigned MI | Lets the deployed `ListDataverseRows` action call the connector |
| `connector-namespace-msi` | Connector Namespace system MI | Required for the namespace to poll the trigger |

Invoke it after deploying (get the function key from the portal or `az functionapp keys list`):

```bash
curl "https://<functionAppName>.azurewebsites.net/api/rows?table=accounts&top=5&code=<function-key>"
```

The response is `{ "table": ..., "count": N, "value": [ ...rows... ] }`.

## Run locally

```bash
pip install -r requirements.txt
func start
```

Set `COMMONDATASERVICE_CONNECTION_RUNTIME_URL` (the connection's runtime URL),
`DATAVERSE_ENVIRONMENT_URL` (the Dataverse org URL), and the table in
`local.settings.json` before starting. Locally the action
uses your signed-in `az login` (user) identity (`AzureCliCredential`). To call the action from your
machine, grant your own identity an access policy on the connection first:

```bash
az connector-namespace connection access-policy create -g <resourceGroup> \
  --namespace <connectorNamespaceName> --connection-name <connectionName> -n dev-user \
  --principal '{"type":"ActiveDirectory","identity":{"objectId":"<your-object-id>","tenantId":"<tenant-id>"}}'
```

The connector trigger needs the **Preview** Functions Extension Bundle, already configured in `host.json`.

## Verify

The Dataverse connector namespace can be **viewed** in the portal once created via ARM/CLI, but
**creating or updating** connections and trigger configs isn't supported there yet — so drive those
from the CLI. Capture the names created by `azd up`:

```bash
RG=$(azd env get-value resourceGroupName)
NS=$(azd env get-value connectorNamespaceName)
CONN=$(azd env get-value connectorNamespaceConnectionName)
FUNC=$(azd env get-value dataverseFunctionName)
TRIGGER="${CONN}-$(echo "$FUNC" | tr '[:upper:]' '[:lower:]')"
```

- **Connection is authenticated** (`overallStatus` should be `Connected`):

  ```bash
  az connector-namespace connection show -g $RG --namespace $NS -n $CONN \
    --query "{name:name, status:properties.overallStatus}" -o jsonc
  ```

- **Trigger config is enabled**:

  ```bash
  az connector-namespace trigger show -g $RG --namespace $NS -n $TRIGGER \
    --query "{state:properties.state, operation:properties.operationName}" -o jsonc
  ```

Now **add a new row** to the configured table (e.g. create an account), wait one polling interval
(5 minutes in this sample), then tail the function logs to see the trigger fire:

```bash
az functionapp log tail -g $RG -n $(azd env get-value functionAppName)
```

> **Permissions note:** these row triggers are **Admin Only** — the OAuth-connected Dataverse
> identity needs **Global Read** on the selected table, or the poll fails with `403 Forbidden`.

## More

- [Operations to Functions Signature Mapping](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md)
- [Common Data Service connector reference](https://learn.microsoft.com/en-us/connectors/commondataservice/)
