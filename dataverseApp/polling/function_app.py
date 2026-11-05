# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

"""Receive current Dataverse events without inspecting their raw payloads."""

import logging

import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="OnDataverseRowAdded")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnDataverseRowAddedTriggerConfigName%",
)
def on_dataverse_row_added(payload: str) -> None:
    """Receive the separate row-added operation as raw JSON."""
    logging.info("Received OnDataverseRowAdded trigger")


@app.function_name(name="OnDataverseRowModified")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnDataverseRowModifiedTriggerConfigName%",
)
def on_dataverse_row_modified(payload: str) -> None:
    """Receive the separate row-modified operation as raw JSON."""
    logging.info("Received OnDataverseRowModified trigger")


@app.function_name(name="OnDataverseRowDeleted")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnDataverseRowDeletedTriggerConfigName%",
)
def on_dataverse_row_deleted(payload: str) -> None:
    """Receive the separate row-deleted operation as raw JSON."""
    logging.info("Received OnDataverseRowDeleted trigger")


@app.function_name(name="OnDataverseRowChanged")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnDataverseRowChangedTriggerConfigName%",
)
def on_dataverse_row_changed(payload: str) -> None:
    """Receive added, modified, or deleted rows without inspecting the payload."""
    logging.info("Received OnDataverseRowChanged trigger")


@app.function_name(name="OnDataverseActionPerformed")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnDataverseActionPerformedTriggerConfigName%",
)
def on_dataverse_action_performed(payload: str) -> None:
    """Receive action-performed events without inspecting the payload."""
    logging.info("Received OnDataverseActionPerformed trigger")