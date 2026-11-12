# Azure DevOps connector triggers (Python)

Choose one independent Function App project:

- [Polling](polling/README.md): Connector Namespace queues source events; the Function App receives and acknowledges them.
- [Webhook](webhook/README.md): Connector Namespace sends events to the deployed Function App's connector callback.

Both projects register the same nine events. Each handler accepts a typed list from `azurefunctions.extensions.connectors.visualstudioteamservices`, logs only the trigger name and item count, and returns `None`. The extension converts payloads into SDK items; handlers do not log fields or return payloads.

| Events | Handler item type |
|---|---|
| Build completed | `devops.BuildResult` |
| Git pull request created or closed | `devops.GitPullRequest` |
| Git push | `devops.GitPush` |
| TFVC check-in | `devops.TfvcChangeset` |
| Work item assigned, closed, created, or updated | `devops.TriggerWorkItemResponse` |

Install each mode's requirements, including `azurefunctions-extensions-connectors>=1.0.0b4`, and use a package build that contains the Azure DevOps bindings above. The version floor matches the Planner sample and the current extension source version; it does not establish that a published 1.0.0b4 wheel contains these bindings. Offline conversion checks use the local extension and connector SDK source checkouts, not a published-wheel installation.

The event names and webhook contract follow the Node sample at revision `158d7e9944caa99f12ec481f1a837320720916d6`. Its typed contexts use the same five item models and normalize Connector Namespace callbacks with an item in `body` or an array in `body.value`. The Python converter accepts these item batches in both delivery modes. This is not a direct Azure DevOps service-hook receiver: an envelope with `eventType` and `resource` needs separate normalization and is not the item contract tested here. Required parameter names follow the generated Python connector's `TRIGGER_OPERATIONS` metadata at revision `ef2011621f4ad64838a8a18c5720aef840fdfe46`. The hook checks the live exported Swagger again before registering sources.

Polling is an additional delivery-mode adaptation, not a feature demonstrated by the pinned Node webhook sample. All nine sources can be selected for Poll delivery; registration and end-to-end delivery still need validation in a supported preview region. These files do not claim live deployment or event-delivery results.

Each mode owns its Bicep, host configuration, input file, requirements, and shell hooks. Only the standard-library setup helper is shared within this app. Use different azd environment names for the two modes.

Source selection is a reviewed JSON file, not an interactive picker. Missing or malformed input and missing required wire keys fail locally before any CLI call. Unknown filters or unsupported schemas fail after the read-only Swagger check, before source or app-settings writes. Browser consent is the only interactive step; an already Connected EntraOAuth connection needs no prompt.