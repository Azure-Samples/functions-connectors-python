# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json
import logging
import os

from azure.connectors import (
    AzureIdentityTokenProvider,
    CommondataserviceClient,
    ConnectorException,
)
from azure.identity.aio import AzureCliCredential, ManagedIdentityCredential

app = func.FunctionApp()

# Dataverse target + connection read from app settings once at startup.
DATAVERSE_ENVIRONMENT = os.environ.get(
    "DATAVERSE_ENVIRONMENT_URL"
) or os.environ.get("DATAVERSE_ENVIRONMENT_NAME", "<unset>")
DATAVERSE_TABLE = os.environ.get("DATAVERSE_TABLE_NAME", "accounts")
RUNTIME_URL = os.environ.get("COMMONDATASERVICE_CONNECTION_RUNTIME_URL")
# Azure injects IDENTITY_ENDPOINT when managed identity is available -> use
# it to pick the credential (MI in Azure, `az login` locally).
IN_AZURE = bool(os.environ.get("IDENTITY_ENDPOINT"))


# ------------------------------------------------------------------------------
# OnDataverseRowChanged — Dataverse connector trigger (GetOnNewItems_V2).
#
# Fires when a new row is added to the configured table. The post-deploy script
# creates the trigger config (connector=commondataservice, operation=
# GetOnNewItems_V2) with dataset=<org URL> and table=<entity set plural name>.
# The connector polls Dataverse server-side and posts each new row to this
# function's connector webhook callback.
# ------------------------------------------------------------------------------
@app.function_name(name="OnDataverseRowChanged")
@app.connector_trigger(arg_name="payload")
def on_dataverse_row_changed(payload: str) -> None:
    """Triggered when a new Dataverse row is added."""
    logging.info("OnDataverseRowChanged trigger received.")

    logging.info(
        f"Environment: '{DATAVERSE_ENVIRONMENT}', Table: '{DATAVERSE_TABLE}'."
    )

    data = json.loads(payload)

    # The connector delivers a batch under body.value; fall back to a single
    # object body for connectors/versions that post one notification at a time.
    body = data.get("body", data)
    rows = body.get("value") if isinstance(body, dict) else None
    if rows is None:
        rows = [body]

    for row in rows:
        if not isinstance(row, dict):
            continue

        # The payload is the newly added Dataverse row. The connector tags each
        # item with an "ItemInternalId"; the row's primary key is "<entity>id"
        # (e.g. accountid), derived from the singular table name.
        singular = (
            DATAVERSE_TABLE[:-1]
            if DATAVERSE_TABLE.endswith("s")
            else DATAVERSE_TABLE
        )
        record_id = (
            row.get("ItemInternalId")
            or row.get(f"{singular}id")
            or "<unset>"
        )

        logging.info(f"New '{DATAVERSE_TABLE}' row id: '{record_id}'.")
        logging.info(f"Columns in payload: {list(row.keys())}.")

    logging.info(f"Batch contains '{len(rows)}' new row(s).")


# ------------------------------------------------------------------------------
# ListDataverseRows — Dataverse connector action (List rows).
#
# Demonstrates *calling* a connector action (not just receiving a trigger)
# with the typed `azure-connectors` SDK:
# CommondataserviceClient.list_records_async targets the connection's runtime
# URL and returns the parsed OData rows. The SDK gets an API Hub token via the
# token provider; the call is authorized by the `functionapp-msi` access
# policy on the connection. Auth is explicit per environment (not
# DefaultAzureCredential): managed identity in Azure, the signed-in
# `az login` (user) identity locally.
#
#   GET /api/rows?table=accounts&top=5
# ------------------------------------------------------------------------------
@app.function_name(name="ListDataverseRows")
@app.route(route="rows", methods=["GET"])
async def list_dataverse_rows(req: func.HttpRequest) -> func.HttpResponse:
    """List rows from the configured Dataverse table via the connector."""
    logging.info("ListDataverseRows action invoked.")

    if not RUNTIME_URL:
        return func.HttpResponse(
            "COMMONDATASERVICE_CONNECTION_RUNTIME_URL is not configured.",
            status_code=500,
        )

    # Table and row count are overridable per request; else the default.
    table = req.params.get("table") or DATAVERSE_TABLE
    top = req.params.get("top", "5")

    credential = (
        ManagedIdentityCredential() if IN_AZURE else AzureCliCredential()
    )

    try:
        async with credential:
            token_provider = AzureIdentityTokenProvider(credential)
            async with CommondataserviceClient(
                RUNTIME_URL, token_provider=token_provider
            ) as client:
                payload = await client.list_records_async(
                    entity_name=table, top=str(top)
                )
    except ConnectorException as error:
        logging.error(
            f"Connector action failed ({error.status_code}): "
            f"{error.response_body}"
        )
        return func.HttpResponse(
            error.response_body,
            status_code=error.status_code,
            mimetype="application/json",
        )

    rows = payload.get("value", []) if isinstance(payload, dict) else []
    logging.info(f"Retrieved '{len(rows)}' row(s) from table '{table}'.")

    return func.HttpResponse(
        json.dumps({"table": table, "count": len(rows), "value": rows}),
        status_code=200,
        mimetype="application/json",
    )
