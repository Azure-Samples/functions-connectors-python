# Azure Functions connectors samples (Python)

This repository contains Python samples that show how to use the new **Connector Namespace** integration with Azure Functions. Each sample lives in its own folder so you can clone, deploy, and explore independently with a single `azd up`.

## What are Functions connectors?

Azure Functions integrates with the managed connectors platform that backs Logic Apps and Power Platform, giving your functions:

- **Connector triggers** — a function runs when an event occurs in an external service (new email in Office 365, file added to SharePoint or OneDrive, message posted to Microsoft Teams, and many more). The runtime exposes a `connector_trigger` binding that receives webhook callbacks from the Connector Namespace.
- **Connector SDK actions** — function code calls connector operations through strongly-typed clients or through dynamic payload models for any connector.

The connector platform handles webhook registration, OAuth flows, token refresh, and retry.

> [!NOTE]
> Connectors in Azure Functions are in **public preview**.

## Prerequisites

- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Azure CLI (`az`)](https://learn.microsoft.com/cli/azure/install-azure-cli) ≥ 2.75.0
- [A supported Python version](https://learn.microsoft.com/azure/azure-functions/functions-versions?tabs=isolated-process%2Cv4&pivots=programming-language-python#languages)
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

- `jq` (for bash post-deploy scripts on macOS/Linux)


## Getting-started samples

Eight self-contained Azure Functions apps, each deployable with `azd up`:

The included deployment templates use Python 3.14 on Flex Consumption.

| App | Connector | Triggers demonstrated |
|---|---|---|
| [`azureblobApp/`](./azureblobApp) | Azure Blob | `OnAzureBlobUpdatedFile` |
| [`dataverseApp/`](./dataverseApp) | Microsoft Dataverse (Common Data Service) | `OnDataverseRowChanged` (when a new row is added) |
| [`kustoApp/`](./kustoApp) | Azure Data Explorer (Kusto) | `OnKustoQueryResult` |
| [`office365App/`](./office365App) | Office 365 Outlook | `OnNewEmail`, `OnFlaggedEmail`, `OnNewMentionMeEmail`, `OnNewCalendarEvent`, `OnUpcomingEvent` |
| [`onedriveApp/`](./onedriveApp) | OneDrive for Business | `OnOneDriveNewFile`, `OnOneDriveUpdatedFile` |
| [`sharepointApp/`](./sharepointApp) | SharePoint Online | `OnSharepointNewFile`, `OnSharepointUpdatedFile` |
| [`teamsApp/`](./teamsApp) | Microsoft Teams | `OnNewChannelMessage`, `OnNewChannelMessageMentioningMe`, `OnGroupMembershipAdd`, `OnGroupMembershipRemoval` |
| [`genericApp/`](./genericApp) | _any connector_ — uses the generic `str` payload | Azure Blob, Office 365, SharePoint, Teams + a custom-type example |

## The packages these samples use

| Package | Role |
|---|---|
| [`azure-functions>=2.3.0b1`](https://pypi.org/project/azure-functions/) | The Functions Python SDK. Provides `@app.connector_trigger` and the broader bindings surface. |
| [`azurefunctions-extensions-connectors>=1.0.0b4`](https://pypi.org/project/azurefunctions-extensions-connectors/) | Supported connector trigger rich SDK-type bindings backed by `azure-connectors` models. |


## What each sample shows

### `azureblobApp` — Azure Blob

A single function `OnAzureBlobUpdatedFile` that fires when blobs in a watched Azure Blob container are updated. It keeps a raw `str` payload and parses JSON fields such as `Name`, `Path`, `Size`, and `LastModified`: the target extension has no supported Azure Blob trigger type binding.

### `dataverseApp` — Microsoft Dataverse (Common Data Service)

A single function `OnDataverseRowChanged` that fires when a new row is **added** to a Dataverse table (operation `GetOnNewItems_V2`). Its target binding is `list[commondataservice.Item]`; read table columns from each item's `dynamic_properties`. The **environment** and **table name** are configurable via `azd env set`. Supply the environment by friendly name (`DATAVERSE_ENVIRONMENT_NAME`, auto-resolved to the org URL via Global Discovery) or explicit URL (`DATAVERSE_ENVIRONMENT_URL`), plus `DATAVERSE_TABLE_NAME` (the entity set / plural name, e.g. `accounts`). The environment URL is passed to the trigger as the `dataset` value. Note: these row triggers are Admin Only and require Global Read on the table.

### `kustoApp` — Azure Data Explorer (Kusto)

`OnKustoQueryResult` runs whenever the configured Kusto query produces a non-empty result. It keeps a raw `str` payload and parses the JSON rows because the target extension has no supported Kusto trigger type binding.

### `office365App` — Office 365 Outlook (typed trigger bindings)

Five Outlook triggers with these target bindings from `azurefunctions.extensions.connectors.office365`:

| Function | Type | Fires when… |
|---|---|---|
| `OnNewEmail` | `list[office365.GraphClientReceiveMessage]` | A new email lands in the watched mailbox / folder |
| `OnFlaggedEmail` | `list[office365.GraphClientReceiveMessage]` | An email is flagged (follow-up) |
| `OnNewMentionMeEmail` | `list[office365.GraphClientReceiveMessage]` | A new email @-mentions the connection identity |
| `OnNewCalendarEvent` | `list[office365.GraphCalendarEventClientReceive]` | A new calendar event is created |
| `OnUpcomingEvent` | `list[office365.GraphCalendarEventClientReceive]` | A calendar event is about to start |

### `onedriveApp` — OneDrive for Business

`OnOneDriveNewFile` and `OnOneDriveUpdatedFile` both target `list[onedriveforbusiness.BlobMetadata]`.
Read file metadata through `name`, `path`, `size`, and `last_modified` attributes.

### `sharepointApp` — SharePoint Online

`OnSharepointNewFile` and `OnSharepointUpdatedFile` both target `list[sharepointonline.Item]`.
Read `dynamic_properties` using exact keys such as `{Name}`, `{Path}`, `{FilenameWithExtension}`,
and `Modified`; these are not fixed Python attributes or OneDrive metadata keys.

### `teamsApp` — Microsoft Teams

Four Teams triggers. The two message handlers target `list[teams.ChatMessage]`, whose `body`
and `from_` fields remain dictionaries. Both membership handlers target
`list[teams.OnGroupMemberChangeResponse]`; the item type is a dictionary alias, so use dictionary keys.

| Function | Fires when… |
|---|---|
| `OnNewChannelMessage` | A new channel message is posted |
| `OnNewChannelMessageMentioningMe` | A channel message @-mentions the connection identity |
| `OnGroupMembershipAdd` | A user is added to a Teams group |
| `OnGroupMembershipRemoval` | A user is removed from a Teams group |

### `genericApp` — generic `connector_trigger` API

Demonstrates the generic API that works for any Azure Logic Apps connector — including connectors that do not have a supported trigger type binding. All five handlers intentionally retain `str` payloads parsed manually, even where a typed alternative exists.

| Function | Connector |
|---|---|
| `OnGenericAzureBlobUpdated` | Azure Blob |
| `OnGenericOffice365NewEmail` | Office 365 |
| `OnGenericSharepointNewFile` | SharePoint Online |
| `OnGenericTeamsChannelMessage` | Teams |
| `OnGenericCustomConnectorEvent` | _any custom connector_ |


## Related repos

| Repo | Purpose |
|---|---|
| [Azure/connectors-python-SDK](https://github.com/Azure/connectors-python-SDK) | `azure-connectors` — Python SDK for Azure Connectors. |
| [Azure/azure-functions-python-extensions](https://github.com/Azure/azure-functions-python-extensions) | `azurefunctions-extensions-connectors` — the binding extension consumed by these samples. |