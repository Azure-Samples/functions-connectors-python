# Copyright (c) Microsoft Corporation.  All rights reserved.
"""Receive Salesforce records through the connector extension webhook."""

import logging
from typing import List

import azure.functions as func
import azurefunctions.extensions.connectors.salesforce as salesforce

app = func.FunctionApp()


@app.function_name(name="OnSalesforceNewItems")
@app.connector_trigger(arg_name="records", connection="ConnectorNamespace")
def on_salesforce_new_items(records: List[salesforce.Item]) -> None:
    """Count new records without logging record contents."""
    logging.info("OnSalesforceNewItems: %d records", len(records))


@app.function_name(name="OnSalesforceUpdatedItems")
@app.connector_trigger(arg_name="records", connection="ConnectorNamespace")
def on_salesforce_updated_items(records: List[salesforce.Item]) -> None:
    """Count changed records without logging record contents."""
    logging.info("OnSalesforceUpdatedItems: %d records", len(records))