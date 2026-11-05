# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import json
import logging

import azure.functions as func

app = func.FunctionApp()


def _parse_files(payload: str) -> list[dict]:
    """Read blob metadata from a direct record or a connector response envelope."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError("Blob trigger payload must contain valid JSON.") from error

    if isinstance(data, dict) and "body" in data:
        data = data["body"]
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as error:
                raise ValueError("Blob trigger body must contain valid JSON.") from error

    if data is None:
        return []
    if not isinstance(data, dict):
        raise ValueError("Blob trigger payload or body must be a metadata object or a collection envelope.")

    if "value" in data:
        files = data["value"]
        if files is None:
            return []
        if not isinstance(files, list):
            raise ValueError("Blob trigger 'value' must be an array or null.")
        if not all(isinstance(record, dict) for record in files):
            raise ValueError("Blob trigger 'value' array must contain only metadata objects.")
        return files

    return [data] if data else []


@app.function_name(name="OnAzureBlobUpdatedFile")
@app.connector_trigger(
    arg_name="payload",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnAzureBlobUpdatedFileTriggerConfigName%",
)
def on_azure_blob_updated_file(payload: str) -> None:
    """Log blob metadata received through the connector trigger."""
    logging.info("OnAzureBlobUpdatedFile trigger received.")

    files = _parse_files(payload)
    for file in files:
        logging.info("Name: '%s'.", file.get("Name"))
        logging.info("Path: '%s'.", file.get("Path"))
        logging.info("Size: '%s'.", file.get("Size"))
        logging.info("LastModified: '%s'.", file.get("LastModified"))

    logging.info("Batch contains '%s' blob(s).", len(files))