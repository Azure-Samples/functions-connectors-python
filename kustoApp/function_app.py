# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json
import logging

app = func.FunctionApp()


@app.function_name(name="OnKustoQueryResult")
@app.connector_trigger(arg_name="payload")
def on_kusto_query_result(payload: str) -> None:
    """Triggered when a Kusto query returns results via connector."""
    logging.info("OnKustoQueryResult trigger received.")

    data = json.loads(payload)
    rows = data.get("body", {}).get("value", [])

    for row in rows:
        logging.info(f"Row: '{json.dumps(row)}'.")

    logging.info(f"Batch contains '{len(rows)}' row(s).")
