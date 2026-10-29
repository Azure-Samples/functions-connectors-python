# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import json
import logging

import azure.functions as func
import azurefunctions.extensions.connectors.teams as teams

app = func.FunctionApp()


@app.function_name(name="OnNewChannelMessage")
@app.connector_trigger(arg_name="messages")
def on_new_channel_message(messages: list[teams.ChatMessage]) -> None:
    """Triggered when a new message is posted in a Teams channel."""
    logging.info("OnNewChannelMessage trigger received.")

    for message in messages:
        from_user = (message.from_ or {}).get("user") or {}
        body = message.body or {}
        logging.info(f"Id: '{message.id}'.")
        logging.info(f"From: '{from_user.get('displayName')}'.")
        logging.info(f"Content: '{body.get('content')}'.")


@app.function_name(name="OnNewChannelMessageMentioningMe")
@app.connector_trigger(arg_name="messages")
def on_new_channel_message_mentioning_me(messages: list[teams.ChatMessage]) -> None:
    """Triggered when a new message mentioning the current user is posted in a Teams channel."""
    logging.info("OnNewChannelMessageMentioningMe trigger received.")

    for message in messages:
        from_user = (message.from_ or {}).get("user") or {}
        body = message.body or {}
        logging.info(f"Id: '{message.id}'.")
        logging.info(f"From: '{from_user.get('displayName')}'.")
        logging.info(f"Content: '{body.get('content')}'.")


@app.function_name(name="OnGroupMembershipAdd")
@app.connector_trigger(arg_name="members")
def on_group_membership_add(members: list[teams.OnGroupMemberChangeResponse]) -> None:
    """Triggered when a member is added to a Teams group."""
    logging.info("OnGroupMembershipAdd trigger received.")

    for member in members:
        logging.info(f"Member: '{json.dumps(member)}'.")


@app.function_name(name="OnGroupMembershipRemoval")
@app.connector_trigger(arg_name="members")
def on_group_membership_removal(members: list[teams.OnGroupMemberChangeResponse]) -> None:
    """Triggered when a member is removed from a Teams group."""
    logging.info("OnGroupMembershipRemoval trigger received.")

    for member in members:
        logging.info(f"Member: '{json.dumps(member)}'.")
