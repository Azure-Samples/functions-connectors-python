# Azure DevOps connector triggers (Python)

Choose one independent, copyable Function App project. Each mode contains its own infrastructure, shell hooks, standard-library setup helper, ignore rules and complete setup instructions:

- [Polling](polling/README.md): provision a foundation, complete Entra consent and interactive source selection, register enabled Poll configs, provision the app with its endpoint and listener settings, then deploy code.
- [Webhook](webhook/README.md): provision and deploy the app, then complete Entra consent and register callbacks from a reviewed mode-local input file.

Use distinct azd environments. Neither mode needs this parent directory at runtime. Both validate ownership before updating sources, disable only owned deselected configs, and preserve unrelated app settings on reprovision. Connection policies grant access to the developer and Function App, not to the namespace itself.

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

The event inventory follows Node webhook revision `158d7e9944caa99f12ec481f1a837320720916d6`. Required wire names follow Python trigger metadata revision `ef2011621f4ad64838a8a18c5720aef840fdfe46`. Each mode checks live exported Swagger before source writes.

The converter accepts typed item batches, including Connector Namespace `body` and `body.value` callbacks. Direct Azure DevOps service-hook envelopes with `eventType` and `resource` need separate normalization. Polling adapts the same inventory to Poll delivery; the pinned Node sample does not establish regional Poll support for every operation.

Offline checks do not prove published-wheel contents, bundle startup, regional availability or live delivery. Consent, source creation, callbacks, queue delivery and acknowledgement still need validation in a supported preview region. Each mode documents permissions, setup, reruns and cleanup inline.