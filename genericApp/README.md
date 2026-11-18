# Generic connector triggers (Python)

Receive raw `str` payloads from any connector operation. Choose [polling](polling/README.md) (the host pulls events; no public endpoint) or [webhook](webhook/README.md) (the Connector Namespace calls the deployed function). Both define one function, `OnGenericConnectorEvent`, and log only its name.

These apps do not provision Azure resources: they use an existing Function App, Connector Namespace, authorized connection, and trigger configs that you create following the [connector trigger configuration guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md).
