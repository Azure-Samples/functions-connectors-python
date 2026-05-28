# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import json
import logging

app = func.FunctionApp()


@app.function_name(name="OnNewChannelMessage")
@app.connector_trigger(arg_name="payload")
def on_new_channel_message(payload: str) -> None:
    """Triggered when a new message is posted in a Teams channel."""
    logging.info("OnNewChannelMessage trigger received.")

    data = json.loads(payload)
    messages = data.get("body", {}).get("value", [])

    for message in messages:
        from_user = message.get("from", {}).get("user", {})
        body = message.get("body", {})
        logging.info(f"Id: '{message.get('id')}'.")
        logging.info(f"From: '{from_user.get('displayName')}'.")
        logging.info(f"Content: '{body.get('content')}'.")


@app.function_name(name="OnNewChannelMessageMentioningMe")
@app.connector_trigger(arg_name="payload")
def on_new_channel_message_mentioning_me(payload: str) -> None:
    """Triggered when a new message mentioning the current user is posted in a Teams channel."""
    logging.info("OnNewChannelMessageMentioningMe trigger received.")

    data = json.loads(payload)
    messages = data.get("body", {}).get("value", [])

    for message in messages:
        from_user = message.get("from", {}).get("user", {})
        body = message.get("body", {})
        logging.info(f"Id: '{message.get('id')}'.")
        logging.info(f"From: '{from_user.get('displayName')}'.")
        logging.info(f"Content: '{body.get('content')}'.")


@app.function_name(name="OnGroupMembershipAdd")
@app.connector_trigger(arg_name="payload")
def on_group_membership_add(payload: str) -> None:
    """Triggered when a member is added to a Teams group."""
    logging.info("OnGroupMembershipAdd trigger received.")

    data = json.loads(payload)
    members = data.get("body", {}).get("value", [])

    for member in members:
        logging.info(f"Member: '{json.dumps(member)}'.")


@app.function_name(name="OnGroupMembershipRemoval")
@app.connector_trigger(arg_name="payload")
def on_group_membership_removal(payload: str) -> None:
    """Triggered when a member is removed from a Teams group."""
    logging.info("OnGroupMembershipRemoval trigger received.")

    data = json.loads(payload)
    members = data.get("body", {}).get("value", [])

    for member in members:
        logging.info(f"Member: '{json.dumps(member)}'.")
