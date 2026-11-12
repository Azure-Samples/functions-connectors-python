# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Receive typed Azure DevOps callbacks and log only trigger names and counts."""

import logging

import azure.functions as func
import azurefunctions.extensions.connectors.visualstudioteamservices as devops

app = func.FunctionApp()


@app.function_name(name="OnVstsBuildCompleted")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_build_completed(event: list[devops.BuildResult]) -> None:
    """Log a completed build trigger."""
    logging.info("Received OnVstsBuildCompleted trigger with %d items.", len(event))


@app.function_name(name="OnVstsGitPullClosed")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_git_pull_closed(event: list[devops.GitPullRequest]) -> None:
    """Log a closed pull request trigger."""
    logging.info("Received OnVstsGitPullClosed trigger with %d items.", len(event))


@app.function_name(name="OnVstsGitPullCreated")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_git_pull_created(event: list[devops.GitPullRequest]) -> None:
    """Log a new pull request trigger."""
    logging.info("Received OnVstsGitPullCreated trigger with %d items.", len(event))


@app.function_name(name="OnVstsGitPush")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_git_push(event: list[devops.GitPush]) -> None:
    """Log a Git push trigger."""
    logging.info("Received OnVstsGitPush trigger with %d items.", len(event))


@app.function_name(name="OnVstsTfvcCheckIn")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_tfvc_check_in(event: list[devops.TfvcChangeset]) -> None:
    """Log a TFVC check-in trigger."""
    logging.info("Received OnVstsTfvcCheckIn trigger with %d items.", len(event))


@app.function_name(name="OnVstsWorkItemAssigned")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_work_item_assigned(event: list[devops.TriggerWorkItemResponse]) -> None:
    """Log an assigned work item trigger."""
    logging.info("Received OnVstsWorkItemAssigned trigger with %d items.", len(event))


@app.function_name(name="OnVstsWorkItemClosed")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_work_item_closed(event: list[devops.TriggerWorkItemResponse]) -> None:
    """Log a closed work item trigger."""
    logging.info("Received OnVstsWorkItemClosed trigger with %d items.", len(event))


@app.function_name(name="OnVstsWorkItemCreated")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_work_item_created(event: list[devops.TriggerWorkItemResponse]) -> None:
    """Log a new work item trigger."""
    logging.info("Received OnVstsWorkItemCreated trigger with %d items.", len(event))


@app.function_name(name="OnVstsWorkItemUpdated")
@app.connector_trigger(arg_name="event", connection="VstsConnection")
def on_vsts_work_item_updated(event: list[devops.TriggerWorkItemResponse]) -> None:
    """Log an updated work item trigger."""
    logging.info("Received OnVstsWorkItemUpdated trigger with %d items.", len(event))