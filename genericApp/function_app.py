# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json
import logging

app = func.FunctionApp()


# ------------------------------------------------------------------------------
# OnGenericAzureBlobUpdated — Azure Blob connector (generic API)
# ------------------------------------------------------------------------------
@app.function_name(name="OnGenericAzureBlobUpdated")
@app.connector_trigger(arg_name="payload")
def on_generic_azure_blob_updated(payload: str) -> None:
    """Generic API trigger for Azure Blob updated file events."""
    logging.info("OnGenericAzureBlobUpdated (generic API) trigger received.")

    data = json.loads(payload)
    items = data.get("body", {}).get("value", [])

    for file in items:
        logging.info(f"Name: '{file.get('Name')}'.")
        logging.info(f"Path: '{file.get('Path')}'.")
        logging.info(f"LastModified: '{file.get('LastModified')}'.")


# ------------------------------------------------------------------------------
# OnGenericCustomConnectorEvent — Custom connector (generic API)
# ------------------------------------------------------------------------------
@app.function_name(name="OnGenericCustomConnectorEvent")
@app.connector_trigger(arg_name="payload")
def on_generic_custom_connector_event(payload: str) -> None:
    """Generic API trigger for custom connector events."""
    logging.info("OnGenericCustomConnectorEvent (generic API) trigger received.")

    data = json.loads(payload)
    items = data.get("body", {}).get("value", [])

    logging.info(f"Received '{len(items)}' item(s).")

    for item in items:
        item_id = item.get("id", "<unset>")
        item_name = item.get("name", "<unset>")
        logging.info(f"Id: '{item_id}', Name: '{item_name}'.")


# ------------------------------------------------------------------------------
# OnGenericOffice365NewEmail — Office 365 connector (generic API)
# ------------------------------------------------------------------------------
@app.function_name(name="OnGenericOffice365NewEmail")
@app.connector_trigger(arg_name="payload")
def on_generic_office365_new_email(payload: str) -> None:
    """Generic API trigger for Office 365 new email events."""
    logging.info("OnGenericOffice365NewEmail (generic API) trigger received.")

    data = json.loads(payload)
    items = data.get("body", {}).get("value", [])

    for email in items:
        logging.info(f"Subject: '{email.get('subject')}'.")
        logging.info(f"From: '{email.get('from')}'.")


# ------------------------------------------------------------------------------
# OnGenericSharepointNewFile — SharePoint Online connector (generic API)
# ------------------------------------------------------------------------------
@app.function_name(name="OnGenericSharepointNewFile")
@app.connector_trigger(arg_name="payload")
def on_generic_sharepoint_new_file(payload: str) -> None:
    """Generic API trigger for SharePoint new file events."""
    logging.info("OnGenericSharepointNewFile (generic API) trigger received.")

    data = json.loads(payload)
    items = data.get("body", {}).get("value", [])

    for file in items:
        logging.info(f"Name: '{file.get('Name')}'.")
        logging.info(f"Path: '{file.get('Path')}'.")


# ------------------------------------------------------------------------------
# OnGenericTeamsChannelMessage — Teams connector (generic API)
# ------------------------------------------------------------------------------
@app.function_name(name="OnGenericTeamsChannelMessage")
@app.connector_trigger(arg_name="payload")
def on_generic_teams_channel_message(payload: str) -> None:
    """Generic API trigger for Teams channel message events."""
    logging.info("OnGenericTeamsChannelMessage (generic API) trigger received.")

    data = json.loads(payload)
    items = data.get("body", {}).get("value", [])

    for message in items:
        logging.info(f"MessageId: '{message.get('id')}'.")
