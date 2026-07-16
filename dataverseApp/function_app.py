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


# ------------------------------------------------------------------------------
# OnDataverseRowChanged — Microsoft Dataverse connector (generic connector API)
#
# Fires when a new row is added to the configured Dataverse table. The trigger
# config (created in the post-deploy script) targets:
#   connector : commondataservice
#   operation : GetOnNewItems_V2
#   parameters:
#     dataset = <org URL>        -> DATAVERSE_ENVIRONMENT_URL (the DataSet name,
#                                   e.g. https://org.crm.dynamics.com)
#     table   = <table>          -> DATAVERSE_TABLE_NAME (entity set / plural
#                                   logical name, e.g. "accounts")
#
# The connector polls Dataverse server-side (default every few minutes) and posts
# each new row to this function's connector webhook callback.
# ------------------------------------------------------------------------------
@app.function_name(name="OnDataverseRowChanged")
@app.connector_trigger(arg_name="payload")
def on_dataverse_row_changed(payload: str) -> None:
    """Triggered when a new Dataverse row is added."""
    logging.info("OnDataverseRowChanged trigger received.")

    environment = os.environ.get("DATAVERSE_ENVIRONMENT_URL") or os.environ.get(
        "DATAVERSE_ENVIRONMENT_NAME", "<unset>"
    )
    table = os.environ.get("DATAVERSE_TABLE_NAME", "<unset>")
    logging.info(f"Environment: '{environment}', Table: '{table}'.")

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
        singular = table[:-1] if table.endswith("s") else table
        record_id = (
            row.get("ItemInternalId")
            or row.get(f"{singular}id")
            or "<unset>"
        )

        logging.info(f"New '{table}' row id: '{record_id}'.")
        logging.info(f"Columns in payload: {list(row.keys())}.")

    logging.info(f"Batch contains '{len(rows)}' new row(s).")


# ------------------------------------------------------------------------------
# ListDataverseRows — Microsoft Dataverse connector ACTION (List rows)
#
# Demonstrates *calling* a connector action (not just receiving a trigger) with
# the typed `azure-connectors` SDK. A CommondataserviceClient targets the
# connection's runtime URL and invokes the Dataverse "List rows" operation:
#
#   rows = await CommondataserviceClient(runtime_url, token_provider) \
#              .list_records_async(entity_name=table, top="5")
#
# The SDK acquires an API Hub token (https://apihub.azure.com/.default) through
# the token provider and calls the connector; the call is authorized by the
# `functionapp-msi` access policy granted on the connection. Auth is explicit per
# environment (DefaultAzureCredential is not used): in Azure the function app's
# managed identity, and locally the signed-in `az login` (user) identity.
#
#   HTTP:   GET /api/rows?table=accounts&top=5
# ------------------------------------------------------------------------------
@app.function_name(name="ListDataverseRows")
@app.route(route="rows", methods=["GET"])
async def list_dataverse_rows(req: func.HttpRequest) -> func.HttpResponse:
    """List rows from the configured Dataverse table via the connector action."""
    logging.info("ListDataverseRows action invoked.")

    runtime_url = os.environ.get("COMMONDATASERVICE_CONNECTION_RUNTIME_URL")
    if not runtime_url:
        return func.HttpResponse(
            "COMMONDATASERVICE_CONNECTION_RUNTIME_URL is not configured.",
            status_code=500,
        )

    # Table (entity set / plural name) and row count are overridable per request;
    # fall back to app settings.
    table = req.params.get("table") or os.environ.get(
        "DATAVERSE_TABLE_NAME", "accounts"
    )
    top = req.params.get("top", "5")

    # Explicit credential per environment (DefaultAzureCredential is not used):
    #   - In Azure (IDENTITY_ENDPOINT is injected) -> the function app's managed identity.
    #   - Locally (not set) -> the signed-in `az login` (user) identity.
    if os.environ.get("IDENTITY_ENDPOINT"):
        credential = ManagedIdentityCredential()
    else:
        credential = AzureCliCredential()

    try:
        async with credential:
            token_provider = AzureIdentityTokenProvider(credential)
            async with CommondataserviceClient(
                runtime_url, token_provider=token_provider
            ) as client:
                payload = await client.list_records_async(
                    entity_name=table, top=str(top)
                )
    except ConnectorException as error:
        logging.error(
            f"Connector action failed ({error.status_code}): {error.response_body}"
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
