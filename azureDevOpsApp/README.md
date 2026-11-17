# Azure DevOps connector triggers (Python)

Choose one independent, copyable Function App project. Each mode contains its own infrastructure, shell hooks, standard-library setup helper, ignore rules and complete setup instructions:

- [Polling](polling/README.md): provision a foundation, complete Entra consent, select triggers and sources, then provision and deploy the app.
- [Webhook](webhook/README.md): provision and deploy the app, then complete Entra consent, select triggers and sources, and register callbacks.

Both modes offer authenticated organization, project and other source pickers based on live connector metadata. Select at least one trigger; skipped listeners are disabled. Use distinct azd environments. Neither mode needs this parent directory at runtime. Both validate ownership before updating sources, disable only owned deselected configs, and preserve unrelated app settings on reprovision.

Use new azd environments for this sample. Existing `vstsApp` deployments and their `OnVsts` trigger configurations are not migrated or disabled automatically; stop old apps and disable old triggers separately to avoid duplicate subscriptions.

The nine handlers in each mode use `typing.List` annotations from `azurefunctions.extensions.connectors.visualstudioteamservices`, log only names and counts, and return `None`.

| Events | Handler item type |
|---|---|
| Build completed | `devops.BuildResult` |
| Git pull request created or closed | `devops.GitPullRequest` |
| Git push | `devops.GitPush` |
| TFVC check-in | `devops.TfvcChangeset` |
| Work item assigned, closed, created or updated | `devops.TriggerWorkItemResponse` |

## Dependencies and runtime

Each mode installs `azurefunctions-extensions-connectors>=1.0.0`; its dependency supplies the connector SDK. No separate direct `azure-connectors` requirement is needed. Requirements select `azure-functions>=1.27.0b1` below Python 3.13 and `azure-functions>=2.4.0` for Python 3.13+. Use pip's `--pre` option if needed for the older-runtime prerelease. Both local examples and generated Values include `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`. Existing local settings remain unchanged unless you request a refresh; add isolation yourself or use the mode's force-refresh option.

Cloud apps use Python 3.14 Flex Consumption. Both hosts use `Microsoft.Azure.Functions.ExtensionBundle` range `[4.41.2, 5.0.0)`, not the preview bundle.

## Contract and validation limits

The nine trigger operations match the TypeScript Azure DevOps samples. The connector ID remains `visualstudioteamservices`; both modes check live exported Swagger before source writes.

The converter accepts typed item batches, including Connector Namespace `body` and `body.value` callbacks. Direct Azure DevOps service-hook envelopes with `eventType` and `resource` need separate normalization.

Offline checks do not prove published-wheel contents, bundle startup, regional availability or live delivery. Consent, source creation, callbacks, queue delivery and acknowledgement still need validation in a supported preview region. Each mode documents permissions, setup, reruns and cleanup inline.