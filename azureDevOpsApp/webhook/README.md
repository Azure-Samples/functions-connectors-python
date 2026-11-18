# Azure DevOps webhook triggers (Python)

The Connector Namespace calls the deployed function app's callback when an Azure DevOps event occurs.

| Function / connector operation | Binding |
| --- | --- |
| `OnAzureDevOpsBuildCompleted` / [`OnBuildCompleted`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-a-build-completes) | `List[devops.BuildResult]` |
| `OnAzureDevOpsGitPullClosed` / [`OnGitPullClosed`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-a-pull-request-is-closed-(git)) | `List[devops.GitPullRequest]` |
| `OnAzureDevOpsGitPullCreated` / [`OnGitPullCreated`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-a-pull-request-is-created-(git)) | `List[devops.GitPullRequest]` |
| `OnAzureDevOpsGitPush` / [`OnGitPush`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-code-is-pushed-(git)) | `List[devops.GitPush]` |
| `OnAzureDevOpsTfvcCheckIn` / [`OnTfvcCheckIn`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-code-is-checked-in-(tfvc)) | `List[devops.TfvcChangeset]` |
| `OnAzureDevOpsWorkItemAssigned` / [`OnWorkItemAssignedV2`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-a-work-item-is-assigned) | `List[devops.TriggerWorkItemResponse]` |
| `OnAzureDevOpsWorkItemClosed` / [`OnWorkItemClosedV2`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-a-work-item-is-closed) | `List[devops.TriggerWorkItemResponse]` |
| `OnAzureDevOpsWorkItemCreated` / [`OnWorkItemCreatedV2`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-a-work-item-is-created) | `List[devops.TriggerWorkItemResponse]` |
| `OnAzureDevOpsWorkItemUpdated` / [`OnWorkItemUpdatedV2`](https://learn.microsoft.com/connectors/visualstudioteamservices/#when-a-work-item-is-updated) | `List[devops.TriggerWorkItemResponse]` |

Handlers log event names and item counts, not content.

## Prerequisites

- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd), [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) 2.75+, and the [connector-namespace extension](https://github.com/Azure/Connectors/tree/main/public-preview/connector-namespace-cli).
- Python for the deployment hooks, plus PowerShell 7 on Windows.
- Azure permission to create resources and role assignments, such as Owner, or Contributor plus Role Based Access Control Administrator.
- An Azure DevOps account in the organization's home tenant, with project access and permission to manage [service hooks](https://learn.microsoft.com/azure/devops/service-hooks/overview?view=azure-devops#permissions). The organization's tenant policy must allow consent to the connector's Entra application.
- For local runs: [Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local) and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite).

The app deploys on Python 3.14 and uses `azurefunctions-extensions-connectors>=1.0.0`. For older Python versions, see [Python 3.12 and older supported versions](../../README.md#python-312-and-older-supported-versions).

## Deploy to Azure

```bash
az login
azd auth login
azd env new azuredevops-webhook
azd up
```

After deploying the app, `azd up` asks you to:

1. Sign in to the Azure DevOps connection in the browser, if it isn't already connected.
2. Choose **Configure** or **Skip** for each trigger. Configure at least one.
3. For each configured trigger, pick the organization, project, and other inputs from live lists, or type them where no list exists.

Skipped functions are still deployed, with their listeners disabled.

Choices are saved in the azd environment and reused by later `azd up` runs. To choose again, run `azd env set AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS ""`, then `azd up`.

To skip prompts, copy [trigger-inputs.example.json](trigger-inputs.example.json) to `trigger-inputs.json` (ignored by git), keep only the triggers to configure, and replace every placeholder. Each entry is `{ "functionName", "operationName", "parameters": [{ "name", "value" }] }` using connector wire names; `account` is the organization name, not a URL. The file takes precedence over saved choices.

`azd up` also deploys later code changes. To retry after a failure, rerun `azd up`.

| Optional setting | Purpose |
| --- | --- |
| `CONNECTOR_NAMESPACE_LOCATION` | Connector Namespace region (default `brazilsouth`). |

## Local development

1. Start Azurite.
2. Install dependencies:

   ```bash
   python -m venv .venv
   # Activate .venv for your shell.
   python -m pip install -r requirements.txt
   ```

3. Sign in with `az login`, then run `func start --enableAuth`.

`azd up` creates `local.settings.json` if it doesn't exist. To regenerate it, run `sh ./infra/scripts/postdeploy.sh --force-local-settings` (or `./infra/scripts/postdeploy.ps1 -ForceLocalSettings`); this also reruns trigger setup.

Deployed triggers call the cloud app, not your local host. To receive events locally, expose port 7071 through an HTTPS tunnel and create a separate trigger configuration in [Connector Namespaces](https://connectors.azure.com/) with callback `https://<tunnel-host>/runtime/webhooks/connector?functionName=<FunctionName>` and your local `connector_extension` system key as the `code` query parameter. Delete it when finished.

## Test

Trigger a configured event, such as queuing a build, pushing a commit, or creating a work item. Confirm the trigger configurations are enabled in [Connector Namespaces](https://connectors.azure.com/) and check the function logs for the event name and count.

## Deprovision

```bash
azd down --purge
```

Service-hook subscriptions in Azure DevOps may remain; delete any you no longer need from the project's service hooks settings. Never commit credentials or local settings.
