# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import azurefunctions.extensions.connectors.onedriveforbusiness as onedrive

app = func.FunctionApp()


@app.function_name(name="OnOneDriveNewFile")
@app.connector_trigger(arg_name="files")
def on_onedrive_new_file(files: list[onedrive.BlobMetadata]) -> None:
    """Triggered when a new file is created in OneDrive for Business."""
    logging.info("OnOneDriveNewFile trigger received.")

    for file in files:
        logging.info("Name: '%s'.", file.name)
        logging.info("Path: '%s'.", file.path)
        logging.info("Size: '%s'.", file.size)


@app.function_name(name="OnOneDriveUpdatedFile")
@app.connector_trigger(arg_name="files")
def on_onedrive_updated_file(files: list[onedrive.BlobMetadata]) -> None:
    """Triggered when a file is updated in OneDrive for Business."""
    logging.info("OnOneDriveUpdatedFile trigger received.")

    for file in files:
        logging.info("Name: '%s'.", file.name)
        logging.info("Path: '%s'.", file.path)
        logging.info("LastModified: '%s'.", file.last_modified)
