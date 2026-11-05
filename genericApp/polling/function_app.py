# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

"""Receive generic connector events through polling without inspecting payloads."""

import logging

import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="OnGenericConnectorEvent")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%GenericTriggerConfigName%",
)
def on_generic_connector_event(payload: str) -> None:
    """Receive a generic connector event as a raw string."""
    logging.info("OnGenericConnectorEvent (generic API) trigger received.")