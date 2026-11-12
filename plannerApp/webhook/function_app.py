# Copyright (c) Microsoft Corporation.  All rights reserved.
# Licensed under the MIT License.

"""Count Planner webhook events without logging task data."""

import logging

import azure.functions as func
from azurefunctions.extensions.connectors.planner import GetTaskResponseV2

app = func.FunctionApp()


@app.function_name(name="OnPlannerCompleteTask")
@app.connector_trigger(arg_name="tasks", connection="ConnectorNamespace")
def on_planner_complete_task(tasks: list[GetTaskResponseV2]) -> None:
    """Count completed tasks."""
    logging.info("Received OnPlannerCompleteTask trigger (%d items)", len(tasks))


@app.function_name(name="OnPlannerNewTask")
@app.connector_trigger(arg_name="tasks", connection="ConnectorNamespace")
def on_planner_new_task(tasks: list[GetTaskResponseV2]) -> None:
    """Count new tasks."""
    logging.info("Received OnPlannerNewTask trigger (%d items)", len(tasks))


@app.function_name(name="OnPlannerTaskAssignedToMe")
@app.connector_trigger(arg_name="tasks", connection="ConnectorNamespace")
def on_planner_task_assigned_to_me(tasks: list[GetTaskResponseV2]) -> None:
    """Count tasks assigned to the connected user."""
    logging.info("Received OnPlannerTaskAssignedToMe trigger (%d items)", len(tasks))