# Azure DevOps connector triggers (Python)

Choose one independent Function App project:

- [Polling](polling/README.md): Connector Namespace queues source events; the Function App receives and acknowledges them.
- [Webhook](webhook/README.md): Connector Namespace sends events to the deployed Function App's connector callback.

Both projects register the same nine events. Each handler accepts `str`, logs only the trigger name, and returns `None`. The samples do not parse, log, or return payloads. They need only the Azure Functions Python SDK, not a connector SDK or Python connector extension package.

The event names and webhook contract follow the Node sample at revision `158d7e9944caa99f12ec481f1a837320720916d6`. Required parameter names follow the generated Python connector's `TRIGGER_OPERATIONS` metadata at revision `ef2011621f4ad64838a8a18c5720aef840fdfe46`. The hook checks the live exported Swagger again before registering sources. The extension source checkout contains Azure DevOps typed wrappers, but these samples deliberately use the worker's raw string conversion path instead.

Polling is an additional delivery-mode adaptation, not a feature demonstrated by the pinned Node webhook sample. All nine sources can be selected for Poll delivery; registration and end-to-end delivery still need validation in a supported preview region. These files do not claim live deployment or event-delivery results.

Each mode owns its Bicep, host configuration, input file, requirements, and shell hooks. Only the standard-library setup helper is shared within this app. Use different azd environment names for the two modes.

Source selection is a reviewed JSON file, not an interactive picker. Missing or malformed input and missing required wire keys fail locally before any CLI call. Unknown filters or unsupported schemas fail after the read-only Swagger check, before source or app-settings writes. Browser consent is the only interactive step; an already Connected EntraOAuth connection needs no prompt.