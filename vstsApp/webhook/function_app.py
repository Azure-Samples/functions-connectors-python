# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Log Azure DevOps webhook arrival without parsing or exposing raw payloads."""

import logging

import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="OnVstsBuildCompleted")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_build_completed(event: str) -> None:
    """Log a completed build trigger."""
    logging.info("Received OnVstsBuildCompleted trigger.")


@app.function_name(name="OnVstsGitPullClosed")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_git_pull_closed(event: str) -> None:
    """Log a closed pull request trigger."""
    logging.info("Received OnVstsGitPullClosed trigger.")


@app.function_name(name="OnVstsGitPullCreated")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_git_pull_created(event: str) -> None:
    """Log a new pull request trigger."""
    logging.info("Received OnVstsGitPullCreated trigger.")


@app.function_name(name="OnVstsGitPush")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_git_push(event: str) -> None:
    """Log a Git push trigger."""
    logging.info("Received OnVstsGitPush trigger.")


@app.function_name(name="OnVstsTfvcCheckIn")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_tfvc_check_in(event: str) -> None:
    """Log a TFVC check-in trigger."""
    logging.info("Received OnVstsTfvcCheckIn trigger.")


@app.function_name(name="OnVstsWorkItemAssigned")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_work_item_assigned(event: str) -> None:
    """Log an assigned work item trigger."""
    logging.info("Received OnVstsWorkItemAssigned trigger.")


@app.function_name(name="OnVstsWorkItemClosed")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_work_item_closed(event: str) -> None:
    """Log a closed work item trigger."""
    logging.info("Received OnVstsWorkItemClosed trigger.")


@app.function_name(name="OnVstsWorkItemCreated")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_work_item_created(event: str) -> None:
    """Log a new work item trigger."""
    logging.info("Received OnVstsWorkItemCreated trigger.")


@app.function_name(name="OnVstsWorkItemUpdated")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_work_item_updated(event: str) -> None:
    """Log an updated work item trigger."""
    logging.info("Received OnVstsWorkItemUpdated trigger.")