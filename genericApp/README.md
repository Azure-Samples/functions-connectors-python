# Generic connector triggers (Python)

Choose the standalone [polling app](./polling/README.md) or [webhook app](./webhook/README.md).

| App | Functions |
| --- | --- |
| Polling | One connector-neutral `OnGenericConnectorEvent` |
| Webhook | One connector-neutral `OnGenericConnectorEvent` |

All handlers receive raw `str` payloads and log only their trigger names.

**These apps do not provision Azure resources.** Use existing authorized Connector Namespace connections and trigger configurations. There are no `azd up` or postdeploy hooks. Function names route webhook callbacks; names alone do not subscribe to a connector operation. Configure the operation and its parameters in the namespace.

Python 3.13+ requires `azure-functions>=2.4.0b1`; older supported Python versions require `azure-functions>=1.27.0b1` and `PYTHON_ISOLATE_WORKER_DEPENDENCIES=1`. Each requirements file uses Python-version markers. Both apps use the Preview Functions extension bundle and include safe local settings examples.

Follow the [connector configuration guide](https://github.com/Azure/azure-functions-connector-extension/blob/main/docs/connector-trigger-configuration.md) and the selected app's README for identity, endpoint, and callback setup.