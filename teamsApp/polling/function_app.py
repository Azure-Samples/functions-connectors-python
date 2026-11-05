# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

"""Receive Teams events without logging message or membership contents."""

import logging

import azure.functions as func
import azurefunctions.extensions.connectors.teams as teams

app = func.FunctionApp()


@app.function_name(name="OnNewChannelMessage")
@app.connector_trigger(
    arg_name="messages",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%OnNewChannelMessageTriggerConfigName%",
)
def on_new_channel_message(messages: list[teams.ChatMessage]) -> None:
    """Receive new channel messages."""
    logging.info("Received OnNewChannelMessage trigger (%s items)", len(messages))


@app.function_name(name="OnNewChannelMessageMentioningMe")
@app.connector_trigger(
    arg_name="messages",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%OnNewChannelMessageMentioningMeTriggerConfigName%",
)
def on_new_channel_message_mentioning_me(messages: list[teams.ChatMessage]) -> None:
    """Receive channel messages that mention the connected user."""
    logging.info("Received OnNewChannelMessageMentioningMe trigger (%s items)", len(messages))


@app.function_name(name="OnGroupMembershipAdd")
@app.connector_trigger(
    arg_name="members",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%OnGroupMembershipAddTriggerConfigName%",
)
def on_group_membership_add(members: list[teams.OnGroupMemberChangeResponse]) -> None:
    """Receive team membership additions."""
    logging.info("Received OnGroupMembershipAdd trigger (%s items)", len(members))


@app.function_name(name="OnGroupMembershipRemoval")
@app.connector_trigger(
    arg_name="members",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%OnGroupMembershipRemovalTriggerConfigName%",
)
def on_group_membership_removal(members: list[teams.OnGroupMemberChangeResponse]) -> None:
    """Receive team membership removals."""
    logging.info("Received OnGroupMembershipRemoval trigger (%s items)", len(members))


@app.function_name(name="WebhookChatMessageTrigger")
@app.connector_trigger(
    arg_name="payload",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%WebhookChatMessageTriggerTriggerConfigName%",
)
def on_new_chat_message(payload: str) -> None:
    """Receive raw chat events."""
    logging.info("Received WebhookChatMessageTrigger event")


@app.function_name(name="WebhookNewMessageTrigger")
@app.connector_trigger(
    arg_name="payload",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%WebhookNewMessageTriggerTriggerConfigName%",
)
def on_new_chat_or_channel_message(payload: str) -> None:
    """Receive raw chat or channel message events."""
    logging.info("Received WebhookNewMessageTrigger event")


@app.function_name(name="WebhookAtMentionTrigger")
@app.connector_trigger(
    arg_name="payload",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%WebhookAtMentionTriggerTriggerConfigName%",
)
def on_mention(payload: str) -> None:
    """Receive raw mention events."""
    logging.info("Received WebhookAtMentionTrigger event")


@app.function_name(name="WebhookKeywordTrigger")
@app.connector_trigger(
    arg_name="payload",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%WebhookKeywordTriggerTriggerConfigName%",
)
def on_keywords(payload: str) -> None:
    """Receive raw keyword events."""
    logging.info("Received WebhookKeywordTrigger event")


@app.function_name(name="WebhookMessageReactionTrigger")
@app.connector_trigger(
    arg_name="payload",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%WebhookMessageReactionTriggerTriggerConfigName%",
)
def on_reaction(payload: str) -> None:
    """Receive raw reaction events."""
    logging.info("Received WebhookMessageReactionTrigger event")


@app.function_name(name="RecordingTrigger")
@app.connector_trigger(
    arg_name="payload",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%RecordingTriggerTriggerConfigName%",
)
def on_recording_available(payload: str) -> None:
    """Receive raw recording events."""
    logging.info("Received RecordingTrigger event")


@app.function_name(name="TranscriptTrigger")
@app.connector_trigger(
    arg_name="payload",
    delivery_mode=func.DeliveryMode.POLL,
    connection="ConnectorNamespace",
    trigger_config_name="%TranscriptTriggerTriggerConfigName%",
)
def on_transcript_available(payload: str) -> None:
    """Receive raw transcript events."""
    logging.info("Received TranscriptTrigger event")