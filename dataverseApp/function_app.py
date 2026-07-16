# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from azure.identity import AzureCliCredential, ManagedIdentityCredential

app = func.FunctionApp()

# OAuth scope every managed-connector runtime URL expects (the API Hub audience).
APIHUB_SCOPE = "https://apihub.azure.com/.default"


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
# Demonstrates *calling* a connector action (not just receiving a trigger). The
# function authenticates to the connection's runtime URL with the function app's
# managed identity and invokes the connector's "List rows" operation:
#
#   GET {runtimeUrl}/v2/datasets/{dataset}/tables/{table}/items
#
# where {dataset} (the org URL) and {table} (entity set plural name) are each
# double URL-encoded per the connector's `x-ms-url-encoding: "double"` contract.
# The call is authorized by the `functionapp-msi` access policy granted on the
# connection. Auth is explicit per environment: in Azure the function app's
# managed identity, and locally the signed-in `az login` (user) identity.
#
#   HTTP:   GET /api/rows?table=accounts&top=5
# ------------------------------------------------------------------------------
@app.function_name(name="ListDataverseRows")
@app.route(route="rows", methods=["GET"])
def list_dataverse_rows(req: func.HttpRequest) -> func.HttpResponse:
    """List rows from the configured Dataverse table via the connector action."""
    logging.info("ListDataverseRows action invoked.")

    runtime_url = os.environ.get("COMMONDATASERVICE_CONNECTION_RUNTIME_URL")
    if not runtime_url:
        return func.HttpResponse(
            "COMMONDATASERVICE_CONNECTION_RUNTIME_URL is not configured.",
            status_code=500,
        )

    dataset = os.environ.get("DATAVERSE_ENVIRONMENT_URL") or os.environ.get(
        "DATAVERSE_ENVIRONMENT_NAME"
    )
    if not dataset:
        return func.HttpResponse(
            "Set either DATAVERSE_ENVIRONMENT_URL or DATAVERSE_ENVIRONMENT_NAME.",
            status_code=500,
        )

    # Table and row count are overridable per request; fall back to app settings.
    table = req.params.get("table") or os.environ.get(
        "DATAVERSE_TABLE_NAME", "accounts"
    )
    top = req.params.get("top", "5")

    # Both path segments are double URL-encoded (x-ms-url-encoding: "double").
    enc_dataset = urllib.parse.quote(urllib.parse.quote(dataset, safe=""), safe="")
    enc_table = urllib.parse.quote(urllib.parse.quote(table, safe=""), safe="")
    url = (
        f"{runtime_url.rstrip('/')}/v2/datasets/{enc_dataset}"
        f"/tables/{enc_table}/items?$top={urllib.parse.quote(str(top))}"
    )

    # Explicit credential per environment (DefaultAzureCredential is not used):
    #   - In Azure (IDENTITY_ENDPOINT is injected) -> the function app's managed identity.
    #   - Locally (not set) -> the signed-in `az login` (user) identity.
    if os.environ.get("IDENTITY_ENDPOINT"):
        credential = ManagedIdentityCredential()
    else:
        credential = AzureCliCredential()

    token = credential.get_token(APIHUB_SCOPE).token
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        logging.error(f"Connector action failed ({error.code}): {body}")
        return func.HttpResponse(body, status_code=error.code, mimetype="application/json")

    rows = payload.get("value", []) if isinstance(payload, dict) else []
    logging.info(f"Retrieved '{len(rows)}' row(s) from table '{table}'.")

    return func.HttpResponse(
        json.dumps({"table": table, "count": len(rows), "value": rows}),
        status_code=200,
        mimetype="application/json",
    )
