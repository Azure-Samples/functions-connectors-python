# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import azurefunctions.extensions.connectors.sharepointonline as sharepoint

app = func.FunctionApp()


@app.function_name(name="OnSharepointNewFile")
@app.connector_trigger(arg_name="files")
def on_sharepoint_new_file(files: list[sharepoint.Item]) -> None:
    """Triggered when a new file is created in SharePoint Online."""
    logging.info("OnSharepointNewFile trigger received.")

    for file in files:
        columns = file.dynamic_properties or {}
        logging.info("Name: '%s'.", columns.get("{FilenameWithExtension}"))
        logging.info("Path: '%s'.", columns.get("{Path}"))
        logging.info("Item ID: '%s'.", columns.get("ID"))


@app.function_name(name="OnSharepointUpdatedFile")
@app.connector_trigger(arg_name="files")
def on_sharepoint_updated_file(files: list[sharepoint.Item]) -> None:
    """Triggered when a file is updated in SharePoint Online."""
    logging.info("OnSharepointUpdatedFile trigger received.")

    for file in files:
        columns = file.dynamic_properties or {}
        logging.info("Name: '%s'.", columns.get("{FilenameWithExtension}"))
        logging.info("Path: '%s'.", columns.get("{Path}"))
        logging.info("LastModified: '%s'.", columns.get("Modified"))
