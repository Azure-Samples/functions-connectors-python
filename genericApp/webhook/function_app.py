# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

"""Receive generic connector webhooks without inspecting payloads."""

import logging

import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="OnGenericAzureBlobUpdated")
@app.connector_trigger(arg_name="payload")
def on_generic_azure_blob_updated(payload: str) -> None:
    """Receive Azure Blob updated file events as a raw string."""
    logging.info("OnGenericAzureBlobUpdated (generic API) trigger received.")


@app.function_name(name="OnGenericCustomConnectorEvent")
@app.connector_trigger(arg_name="payload")
def on_generic_custom_connector_event(payload: str) -> None:
    """Receive custom connector events as a raw string."""
    logging.info("OnGenericCustomConnectorEvent (generic API) trigger received.")


@app.function_name(name="OnGenericOffice365NewEmail")
@app.connector_trigger(arg_name="payload")
def on_generic_office365_new_email(payload: str) -> None:
    """Receive Office 365 new email events as a raw string."""
    logging.info("OnGenericOffice365NewEmail (generic API) trigger received.")


@app.function_name(name="OnGenericSharepointNewFile")
@app.connector_trigger(arg_name="payload")
def on_generic_sharepoint_new_file(payload: str) -> None:
    """Receive SharePoint new file events as a raw string."""
    logging.info("OnGenericSharepointNewFile (generic API) trigger received.")


@app.function_name(name="OnGenericTeamsChannelMessage")
@app.connector_trigger(arg_name="payload")
def on_generic_teams_channel_message(payload: str) -> None:
    """Receive Teams channel message events as a raw string."""
    logging.info("OnGenericTeamsChannelMessage (generic API) trigger received.")