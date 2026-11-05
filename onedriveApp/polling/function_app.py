# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import azurefunctions.extensions.connectors.onedriveforbusiness as onedrive

app = func.FunctionApp()


@app.function_name(name="OnOneDriveNewFileContent")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnOneDriveNewFileContentTriggerConfigName%",
)
def on_onedrive_new_file_content(payload: str) -> None:
    """Receive a newly created file without logging its content."""
    logging.info("OnOneDriveNewFileContent trigger received.")


@app.function_name(name="OnOneDriveUpdatedFileContent")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnOneDriveUpdatedFileContentTriggerConfigName%",
)
def on_onedrive_updated_file_content(payload: str) -> None:
    """Receive a modified file without logging its content."""
    logging.info("OnOneDriveUpdatedFileContent trigger received.")


@app.function_name(name="OnOneDriveNewFile")
@app.connector_trigger(
    arg_name="files",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnOneDriveNewFileTriggerConfigName%",
)
def on_onedrive_new_file(files: list[onedrive.BlobMetadata]) -> None:
    """Triggered when a new file is created in OneDrive for Business."""
    logging.info("OnOneDriveNewFile trigger received.")

    for file in files:
        logging.info("Name: '%s'.", file.name)
        logging.info("Path: '%s'.", file.path)
        logging.info("Size: '%s'.", file.size)


@app.function_name(name="OnOneDriveUpdatedFile")
@app.connector_trigger(
    arg_name="files",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnOneDriveUpdatedFileTriggerConfigName%",
)
def on_onedrive_updated_file(files: list[onedrive.BlobMetadata]) -> None:
    """Triggered when a file is updated in OneDrive for Business."""
    logging.info("OnOneDriveUpdatedFile trigger received.")

    for file in files:
        logging.info("Name: '%s'.", file.name)
        logging.info("Path: '%s'.", file.path)
        logging.info("LastModified: '%s'.", file.last_modified)