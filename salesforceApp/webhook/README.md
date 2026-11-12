# Salesforce webhook delivery

Read the [shared setup, parameter and permission guidance](../README.md) first. This folder is a complete azd project; use a separate environment from polling and run `azd up` here.

Both functions use the default connector webhook binding with `connection="ConnectorNamespace"`, no Poll delivery argument, and no trigger-config-name argument. They receive `list[salesforce.Item]` and log only function name and count. Salesforce's underlying new/updated operations are GET-based connector triggers; webhook here describes delivery from the Connector Namespace to the Function App, not a Salesforce native outbound-message subscription.

Copy [trigger-inputs.example.json](trigger-inputs.example.json) to ignored `trigger-inputs.json`, replace placeholder `table` values with actual reviewed Salesforce object IDs, and remove unwanted events. The hook can prompt instead if no file exists and the terminal is interactive.

The [shared hook](../scripts/setup.py) requires Salesforce `Connected`, checks ownership of both known sources before writes, and verifies the actual Function App `defaultHostName` against the provisioned output. It reads only `systemKeys.connector_extension` for callback authentication. The HTTPS callback uses `/runtime/webhooks/connector?functionName=<function>` and QueryString authentication named `code`. The key remains in memory/private staged JSON and is never a Bicep output or local setting.

After source registration succeeds, the hook applies selected-listener Disabled flags to the cloud app. Reruns keep unchanged sources untouched, preserve other writable properties on updates, and disable deselected owned sources without deleting them. Missing keys, hostname mismatches, failed registration, and foreign/Poll ownership stop setup.

Generated local settings use Azurite and contain no callback key. They do **not** redirect deployed callbacks to your local host. This sample registers cloud callbacks only; local webhook delivery would need a separately reviewed HTTPS tunnel and local extension key setup. Do not point cloud callbacks at localhost or use the app's default/function key in place of the connector system key.

The preview bundle range in [host.json](host.json) is `[4.50.0, 5.0.0)`. The deployed runtime is Python 3.14 on Flex Consumption. No live Salesforce authentication or callback delivery has been validated by local checks.