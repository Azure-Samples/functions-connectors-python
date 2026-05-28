# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json
import logging

app = func.FunctionApp()


@app.function_name(name="OnAzureBlobUpdatedFile")
@app.connector_trigger(arg_name="payload")
def on_azure_blob_updated_file(payload: str) -> None:
    """Triggered when a blob is updated in Azure Blob Storage via connector."""
    logging.info("OnAzureBlobUpdatedFile trigger received.")

    data = json.loads(payload)
    files = data.get("body", {}).get("value", [])

    for file in files:
        logging.info(f"Name: '{file.get('Name')}'.")
        logging.info(f"Path: '{file.get('Path')}'.")
        logging.info(f"Size: '{file.get('Size')}'.")
        logging.info(f"LastModified: '{file.get('LastModified')}'.")

    logging.info(f"Batch contains '{len(files)}' blob(s).")
