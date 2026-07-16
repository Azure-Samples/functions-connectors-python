# Microsoft Dataverse Trigger + Action (Python)

Azure Functions sample app demonstrating the **Microsoft Dataverse** (Common Data Service)
connector using the `azurefunctions-extensions-connectors` connector trigger extension for
the trigger, plus a managed-identity HTTP function that **calls** a connector action.

| Function | Type | Connector operation | Description |
| --- | --- | --- | --- |
| `OnDataverseRowChanged` | Trigger | [`GetOnNewItems_V2`](https://learn.microsoft.com/en-us/connectors/commondataservice/#when-a-row-is-added-(admin-only)-[deprecated]) | Fires when a **new row is added** to the configured Dataverse table |
| `ListDataverseRows` | Action (HTTP) | [List rows](https://learn.microsoft.com/en-us/connectors/commondataservice/#list-rows-(legacy)-[deprecated]) (via `azure-connectors` SDK) | On-demand endpoint that **calls** the connector to list rows from the table |

> **Trigger scope & known issue:** this sample uses the **new-row** trigger `GetOnNewItems_V2`
> (*"When a row is created"*), which is validated end-to-end over the Connector Namespace + Functions
> callback path. The broader `SubscribeWebhookTrigger` (*"When a row is added, modified or deleted"*)
> is **not usable via Connector Namespace yet**: creating its trigger config currently fails with
> **HTTP 500** (a `Regex.Match` null-reference error). The Connector Namespace team is actively working on
> adding `SubscribeWebhookTrigger` support; until it ships, use the `GetOnNewItems_V2` trigger this
> sample demonstrates.

> **Why `commondataservice` (and not `commondataserviceforapps`):** this sample deliberately targets
> the legacy **[`commondataservice`](https://learn.microsoft.com/en-us/connectors/commondataservice/)** connector. Its intended successor, `commondataserviceforapps`,
> has only been shipped to Power Automate and is **not yet available for Logic Apps / Connector
> Namespaces**. By prior consensus with the connector owners, the legacy `commondataservice` connector
> remains supported in production for Connector Namespace until (and unless) the replacement is finally released
> to that environment. Do not switch this sample to `commondataserviceforapps` until it is generally
> available in the Logic Apps / Connector Namespace environment.

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
- [Python 3.13](https://www.python.org/downloads/)
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
| **Flex Consumption Function App** (Python 3.13) | Hosts the trigger + action functions |
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

## Call the connector action (List rows)

Besides *receiving* the trigger, `ListDataverseRows` *calls* the Dataverse **List rows** action
against the connection's runtime URL using the typed
[`azure-connectors`](https://pypi.org/project/azure-connectors/) SDK:

```python
async with CommondataserviceClient(runtime_url, token_provider=token_provider) as client:
    payload = await client.list_records_async(entity_name=table, top="5")
```

The SDK issues the connector's List rows request (`GET {runtimeUrl}/api/data/v9.1/{entity}?$top=5`)
and returns the parsed OData payload — no manual URL building or encoding. The connection's runtime
URL already identifies the Dataverse environment, so the action needs only the **table** (entity set
plural name); it does **not** take the org URL. The SDK's `token_provider` authenticates with a bearer
token for the API Hub scope `https://apihub.azure.com/.default`, using an **explicit credential per
environment** (not `DefaultAzureCredential`): in Azure the function app's **system-assigned managed
identity** (`ManagedIdentityCredential`, no client id), and locally your `az login` (user) identity
(`AzureCliCredential`). The environment is detected via the `IDENTITY_ENDPOINT` variable that Azure
injects when managed identity is available.

> **Why `IDENTITY_ENDPOINT`?** On App Service, Azure Functions, and Container Apps, the platform
> injects the `IDENTITY_ENDPOINT` and `IDENTITY_HEADER` environment variables that expose the local
> managed-identity token endpoint (the `api-version=2019-08-01` MSI REST protocol). These are
> documented by Microsoft and are exactly what the Azure Identity SDK reads under the hood to select
> the App Service / Functions MI source — see
> [Managed identities for App Service and Azure Functions → *Connect to Azure services in app code* (HTTP GET tab)](https://learn.microsoft.com/azure/app-service/overview-managed-identity?tabs=portal%2Chttp#connect-to-azure-services-in-app-code).
> Because the variable is present **iff** the platform MI endpoint is available (and absent locally),
> its presence is a reliable "running in Azure with MI" signal for this host — and it survives Flex
> Consumption, where `WEBSITE_INSTANCE_ID` is *not* set (Flex is not classed as App Service by the
> Functions host).
>
> **Caveat / scope:** this signal is specific to App Service, Functions, and Container Apps. Other
> managed-identity hosts differ — VM/VMSS use the [IMDS endpoint](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/how-to-use-vm-token)
> (`169.254.169.254`) and don't set `IDENTITY_ENDPOINT`, and AKS workload identity uses
> `AZURE_FEDERATED_TOKEN_FILE`. So treat `IDENTITY_ENDPOINT` as the auth-source signal for *this*
> host, not as a general-purpose "am I in Azure?" detector.
>
> **Production guidance:** the local-vs-cloud branch exists purely for developer convenience in this
> sample. A production app should pick **one** credential and use it unconditionally — in Azure that
> means `ManagedIdentityCredential` only (no local/CLI fallback path shipped to the cloud), so there is
> no environment-detection branch to reason about, no accidental fall-through to a developer identity,
> and one deterministic auth path to secure and audit.

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

Set `COMMONDATASERVICE_CONNECTION_RUNTIME_URL` (the connection's runtime URL) and the table in
`local.settings.json` before starting. The action itself needs only the runtime URL and table — the
environment is identified by the connection. Locally the action
uses your signed-in `az login` (user) identity (`AzureCliCredential`). To call the action from your
machine, grant your own identity an access policy on the connection first:

```bash
az connector-namespace connection access-policy create -g <resourceGroup> \
  --namespace <connectorNamespaceName> --connection-name <connectionName> -n dev-user \
  --principal '{"type":"ActiveDirectory","identity":{"objectId":"<your-object-id>","tenantId":"<tenant-id>"}}'
```

The connector trigger needs the **Preview** Functions Extension Bundle, already configured in `host.json`.

## Verify

The Dataverse connector namespace isn't surfaced in the portal yet, so verify from the CLI. Capture
the names created by `azd up`:

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
