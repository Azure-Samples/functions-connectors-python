# Salesforce Poll delivery

Read the [shared setup, parameter and permission guidance](../README.md) first. This folder is a complete azd project; run `azd up` here with a distinct environment name.

Both functions use `connection="ConnectorNamespace"`, explicit `DeliveryMode.POLL`, and `%OnSalesforceNewItemsTriggerConfigName%` or `%OnSalesforceUpdatedItemsTriggerConfigName%`. They receive `list[salesforce.Item]` and log only function name and count.

Copy [trigger-inputs.example.json](trigger-inputs.example.json) to ignored `trigger-inputs.json`, replace the placeholder object IDs with reviewed `GetTables` identifiers, and remove entries you do not want. Alternatively, answer the hook's terminal prompts. Never supply an empty selected `table`.

The infrastructure creates the namespace and Salesforce connection without Poll sources. Initial listeners are disabled. After consent reports `Connected`, the [shared hook](../scripts/setup.py) creates/reconciles selected sources with `deliveryMode: Poll`, verifies registration, and reads their `pollingEndpoints.receiveUri` through bounded GETs.

The helper validates HTTPS and the matching trigger receive path. It keeps the service origin and gateway prefix (including `/api/connectorGateways/...`) and strips only a trailing `/api` suffix before `/triggerConfigs`. All selected sources must agree on the gateway. It writes cloud `ConnectorNamespace__credential=managedidentity`, `ConnectorNamespace__pollingEndpoint`, both trigger-name settings, and selected-listener Disabled flags through a private `--settings @path` file. No callback key is needed.

The hook creates private local settings with the same endpoint/name settings, Azurite storage, and developer authentication, but without the cloud managed-identity credential. Existing local settings stay unchanged unless you explicitly force replacement. If you preserve an older local file after changing selection, update it yourself or rerun with `-ForceLocalSettings`/`--force` before local testing.

The preview bundle range in [host.json](host.json) is `[4.50.0, 5.0.0)`. The deployed runtime is Python 3.14 on Flex Consumption. No live Salesforce or Azure deployment has been validated by this sample's local checks.