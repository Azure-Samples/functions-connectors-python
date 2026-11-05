# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import azurefunctions.extensions.connectors.sharepointonline as sharepoint

app = func.FunctionApp()


@app.function_name(name="OnSharepointNewFile")
@app.connector_trigger(
    arg_name="files",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnSharepointNewFileTriggerConfigName%",
)
def on_sharepoint_new_file(files: list[sharepoint.Item]) -> None:
    """Triggered when a new file is created in SharePoint Online."""
    logging.info("Received OnSharepointNewFile trigger (%s items)", len(files))


@app.function_name(name="OnSharepointUpdatedFile")
@app.connector_trigger(
    arg_name="files",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnSharepointUpdatedFileTriggerConfigName%",
)
def on_sharepoint_updated_file(files: list[sharepoint.Item]) -> None:
    """Triggered when a file is updated in SharePoint Online."""
    logging.info("Received OnSharepointUpdatedFile trigger (%s items)", len(files))


@app.function_name(name="OnSharepointNewItem")
@app.connector_trigger(arg_name="items", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnSharepointNewItemTriggerConfigName%")
def on_sharepoint_new_item(items: list[sharepoint.Item]) -> None:
    """Receive newly created list items."""
    logging.info("Received OnSharepointNewItem trigger (%s items)", len(items))


@app.function_name(name="OnSharepointUpdatedItem")
@app.connector_trigger(arg_name="items", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnSharepointUpdatedItemTriggerConfigName%")
def on_sharepoint_updated_item(items: list[sharepoint.Item]) -> None:
    """Receive created or modified list items."""
    logging.info("Received OnSharepointUpdatedItem trigger (%s items)", len(items))


@app.function_name(name="OnSharepointChangedItem")
@app.connector_trigger(arg_name="items", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnSharepointChangedItemTriggerConfigName%")
def on_sharepoint_changed_item(items: list[sharepoint.Item]) -> None:
    """Receive changed list items."""
    logging.info("Received OnSharepointChangedItem trigger (%s items)", len(items))


@app.function_name(name="OnSharepointDeletedItem")
@app.connector_trigger(arg_name="items", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnSharepointDeletedItemTriggerConfigName%")
def on_sharepoint_deleted_item(items: list[sharepoint.DeletedItem]) -> None:
    """Receive deleted list items when an administrator enables this source."""
    logging.info("Received OnSharepointDeletedItem trigger (%s items)", len(items))


@app.function_name(name="OnSharepointDeletedFile")
@app.connector_trigger(arg_name="items", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnSharepointDeletedFileTriggerConfigName%")
def on_sharepoint_deleted_file(items: list[sharepoint.DeletedItem]) -> None:
    """Receive deleted library files when an administrator enables this source."""
    logging.info("Received OnSharepointDeletedFile trigger (%s items)", len(items))


@app.function_name(name="OnSharepointFormSubmitted")
@app.connector_trigger(arg_name="items", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnSharepointFormSubmittedTriggerConfigName%")
def on_sharepoint_form_submitted(items: list[sharepoint.Item]) -> None:
    """Receive submissions from the selected existing form."""
    logging.info("Received OnSharepointFormSubmitted trigger (%s items)", len(items))


@app.function_name(name="OnSharepointFileClassified")
@app.connector_trigger(arg_name="items", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnSharepointFileClassifiedTriggerConfigName%")
def on_sharepoint_file_classified(items: list[sharepoint.Item]) -> None:
    """Receive classifications from a licensed Microsoft Syntex model."""
    logging.info("Received OnSharepointFileClassified trigger (%s items)", len(items))


@app.function_name(name="OnSharepointRecurringDigest")
@app.connector_trigger(arg_name="items", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnSharepointRecurringDigestTriggerConfigName%")
def on_sharepoint_recurring_digest(items: list[sharepoint.Item]) -> None:
    """Receive updates on the selected connector digest schedule."""
    logging.info("Received OnSharepointRecurringDigest trigger (%s items)", len(items))
