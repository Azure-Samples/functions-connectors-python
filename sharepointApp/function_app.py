# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json
import logging

app = func.FunctionApp()


@app.function_name(name="OnSharepointNewFile")
@app.connector_trigger(arg_name="payload")
def on_sharepoint_new_file(payload: str) -> None:
    """Triggered when a new file is created in SharePoint Online."""
    logging.info("OnSharepointNewFile trigger received.")

    data = json.loads(payload)
    files = data.get("body", {}).get("value", [])

    for file in files:
        logging.info(f"Name: '{file.get('Name')}'.")
        logging.info(f"Path: '{file.get('Path')}'.")
        logging.info(f"Size: '{file.get('Size')}'.")


@app.function_name(name="OnSharepointUpdatedFile")
@app.connector_trigger(arg_name="payload")
def on_sharepoint_updated_file(payload: str) -> None:
    """Triggered when a file is updated in SharePoint Online."""
    logging.info("OnSharepointUpdatedFile trigger received.")

    data = json.loads(payload)
    files = data.get("body", {}).get("value", [])

    for file in files:
        logging.info(f"Name: '{file.get('Name')}'.")
        logging.info(f"Path: '{file.get('Path')}'.")
        logging.info(f"LastModified: '{file.get('LastModified')}'.")
