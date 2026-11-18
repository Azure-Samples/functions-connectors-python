# Azure DevOps connector triggers (Python)

Choose [polling](polling/README.md) (the host pulls events; no public endpoint) or [webhook](webhook/README.md) (the Connector Namespace calls the deployed app). Each folder is a standalone app; use a separate azd environment for each.

| Events | Binding item type |
| --- | --- |
| Build completed | `devops.BuildResult` |
| Git pull request created or closed | `devops.GitPullRequest` |
| Git push | `devops.GitPush` |
| TFVC check-in | `devops.TfvcChangeset` |
| Work item assigned, closed, created or updated | `devops.TriggerWorkItemResponse` |

See the [Azure DevOps connector reference](https://learn.microsoft.com/connectors/visualstudioteamservices/) for trigger inputs and payloads.
