# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json
import logging

app = func.FunctionApp()


@app.function_name(name="OnOneDriveNewFile")
@app.connector_trigger(arg_name="payload")
def on_onedrive_new_file(payload: str) -> None:
    """Triggered when a new file is created in OneDrive for Business."""
    logging.info("OnOneDriveNewFile trigger received.")

    data = json.loads(payload)
    files = data.get("body", {}).get("value", [])

    for file in files:
        logging.info(f"Name: '{file.get('Name')}'.")
        logging.info(f"Path: '{file.get('Path')}'.")
        logging.info(f"Size: '{file.get('Size')}'.")


@app.function_name(name="OnOneDriveUpdatedFile")
@app.connector_trigger(arg_name="payload")
def on_onedrive_updated_file(payload: str) -> None:
    """Triggered when a file is updated in OneDrive for Business."""
    logging.info("OnOneDriveUpdatedFile trigger received.")

    data = json.loads(payload)
    files = data.get("body", {}).get("value", [])

    for file in files:
        logging.info(f"Name: '{file.get('Name')}'.")
        logging.info(f"Path: '{file.get('Path')}'.")
        logging.info(f"LastModified: '{file.get('LastModified')}'.")
