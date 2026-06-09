# Office 365 Outlook Triggers (Python)

Azure Functions sample app demonstrating **Office 365 Outlook** connector triggers using the
`azurefunctions-extensions-connectors` package with the Functions connector trigger extension.

| Function | Connector operation | Description |
| --- | --- | --- |
| `OnNewEmail` | [`OnNewEmailV3`](https://learn.microsoft.com/en-us/connectors/office365/#when-a-new-email-arrives-(v3)) | Fires when a new email arrives |
| `OnFlaggedEmail` | [`OnFlaggedEmailV4`](https://learn.microsoft.com/en-us/connectors/office365/#when-an-email-is-flagged-(v4)) | Fires when an email is flagged |
| `OnNewMentionMeEmail` | [`OnNewMentionMeEmailV3`](https://learn.microsoft.com/en-us/connectors/office365/#when-a-new-email-mentioning-me-arrives-(v3)) | Fires when a new email mentions the authenticated user |
| `OnNewCalendarEvent` | [`CalendarGetOnNewItemsV3`](https://learn.microsoft.com/en-us/connectors/office365/#when-a-new-event-is-created-(v3)) | Fires when a new calendar event is created |
| `OnUpcomingEvent` | [`OnUpcomingEventsV3`](https://learn.microsoft.com/en-us/connectors/office365/#when-an-upcoming-event-is-starting-soon-(v3)) | Fires when an upcoming calendar event is starting soon |

> [!CAUTION]
> **Personal data.** This sample writes email/calendar content to Blob Storage for demonstration only. Restrict access to the resources to appropriate users only, and run `azd down --purge` when done.

## Prerequisites

- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Azure CLI (`az`)](https://learn.microsoft.com/cli/azure/install-azure-cli) ≥ 2.75.0
- [Python 3.13](https://www.python.org/downloads/)
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
cd office365App
azd auth login
az login
azd up
```

### Resources provisioned

| Resource | Purpose |
| --- | --- |
| **Resource Group** | Contains all resources |
| **Flex Consumption Function App** (Python 3.13) | Hosts the 5 connector trigger functions |
| **App Service Plan** (FC1) | Flex Consumption plan |
| **User-Assigned Managed Identity** | Identity for the function app |
| **Storage Account** | Deployment artifacts, function runtime state, and trigger payload output |
| **Log Analytics Workspace** | Backing store for Application Insights |
| **Application Insights** | Telemetry and logging |
| **Connector Namespace** | Hosts the Office 365 connection and trigger configs |
| **Office 365 Outlook Connection** (OAuth) | Authenticates to Office 365 — requires interactive consent during post-deploy |

After provisioning, a post-deploy hook authorizes the Office 365 connection and creates trigger configs. To re-run:

```bash
azd hooks run postdeploy
```

### Trigger configuration

The post-deploy script configures the `OnNewEmail` trigger with these defaults:

| Setting | Value |
| ------- | ----- |
| `operationName` | `OnNewEmailV3` |
| `folderPath` | `Inbox` |
| `importance` | `High` |

Edit `infra/scripts/postdeploy.ps1` (or `.sh`) to change folder, importance, or add trigger configs for the other functions.

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

## Verify

After `azd up`, open the [Connector Namespaces portal](https://connectors.azure.com/) to verify:

- One **Connection** (Office 365 Outlook) with status **Connected**
- Trigger configs in **Enabled** state

Send yourself a high-importance email to fire the trigger. Tail logs with:

```bash
az functionapp log tail -g <resourceGroupName> -n <functionAppName>
```

## More

- [Operations to Functions Signature Mapping](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/operations-functions-match.md)
- [Office 365 Outlook connector reference](https://learn.microsoft.com/en-us/connectors/office365/)
- [Built-in auth sample](https://github.com/Azure-Samples/functions-connectors-net-builtinauth) — secretless authentication using managed identity + Easy Auth.
