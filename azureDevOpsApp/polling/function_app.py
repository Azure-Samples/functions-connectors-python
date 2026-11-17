# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Receive typed Azure DevOps batches and log only trigger names and counts."""

import logging
from typing import List

import azure.functions as func
import azurefunctions.extensions.connectors.visualstudioteamservices as devops

app = func.FunctionApp()


@app.function_name(name="OnAzureDevOpsBuildCompleted")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsBuildCompletedTriggerConfigName%")
def on_azure_devops_build_completed(event: List[devops.BuildResult]) -> None:
    """Log a completed build trigger."""
    logging.info("Received OnAzureDevOpsBuildCompleted trigger with %d items.", len(event))


@app.function_name(name="OnAzureDevOpsGitPullClosed")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsGitPullClosedTriggerConfigName%")
def on_azure_devops_git_pull_closed(event: List[devops.GitPullRequest]) -> None:
    """Log a closed pull request trigger."""
    logging.info("Received OnAzureDevOpsGitPullClosed trigger with %d items.", len(event))


@app.function_name(name="OnAzureDevOpsGitPullCreated")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsGitPullCreatedTriggerConfigName%")
def on_azure_devops_git_pull_created(event: List[devops.GitPullRequest]) -> None:
    """Log a new pull request trigger."""
    logging.info("Received OnAzureDevOpsGitPullCreated trigger with %d items.", len(event))


@app.function_name(name="OnAzureDevOpsGitPush")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsGitPushTriggerConfigName%")
def on_azure_devops_git_push(event: List[devops.GitPush]) -> None:
    """Log a Git push trigger."""
    logging.info("Received OnAzureDevOpsGitPush trigger with %d items.", len(event))


@app.function_name(name="OnAzureDevOpsTfvcCheckIn")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsTfvcCheckInTriggerConfigName%")
def on_azure_devops_tfvc_check_in(event: List[devops.TfvcChangeset]) -> None:
    """Log a TFVC check-in trigger."""
    logging.info("Received OnAzureDevOpsTfvcCheckIn trigger with %d items.", len(event))


@app.function_name(name="OnAzureDevOpsWorkItemAssigned")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsWorkItemAssignedTriggerConfigName%")
def on_azure_devops_work_item_assigned(event: List[devops.TriggerWorkItemResponse]) -> None:
    """Log an assigned work item trigger."""
    logging.info("Received OnAzureDevOpsWorkItemAssigned trigger with %d items.", len(event))


@app.function_name(name="OnAzureDevOpsWorkItemClosed")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsWorkItemClosedTriggerConfigName%")
def on_azure_devops_work_item_closed(event: List[devops.TriggerWorkItemResponse]) -> None:
    """Log a closed work item trigger."""
    logging.info("Received OnAzureDevOpsWorkItemClosed trigger with %d items.", len(event))


@app.function_name(name="OnAzureDevOpsWorkItemCreated")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsWorkItemCreatedTriggerConfigName%")
def on_azure_devops_work_item_created(event: List[devops.TriggerWorkItemResponse]) -> None:
    """Log a new work item trigger."""
    logging.info("Received OnAzureDevOpsWorkItemCreated trigger with %d items.", len(event))


@app.function_name(name="OnAzureDevOpsWorkItemUpdated")
@app.connector_trigger(arg_name="event", connection="ConnectorNamespace", delivery_mode=func.DeliveryMode.POLL,
                       trigger_config_name="%OnAzureDevOpsWorkItemUpdatedTriggerConfigName%")
def on_azure_devops_work_item_updated(event: List[devops.TriggerWorkItemResponse]) -> None:
    """Log an updated work item trigger."""
    logging.info("Received OnAzureDevOpsWorkItemUpdated trigger with %d items.", len(event))