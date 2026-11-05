# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import azurefunctions.extensions.connectors.office365 as office365

app = func.FunctionApp()


# ------------------------------------------------------------------------------
# OnNewEmail — GraphClientReceiveMessage type (OnNewEmailV3)
# ------------------------------------------------------------------------------
@app.function_name(name="OnNewEmail")
@app.connector_trigger(
    arg_name="emails",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnNewEmailTriggerConfigName%",
)
def on_new_email(emails: list[office365.GraphClientReceiveMessage]) -> None:
    """Triggered when a new email arrives in Office 365."""
    logging.info("Received OnNewEmail trigger (%d items)", len(emails))


# ------------------------------------------------------------------------------
# OnFlaggedEmail — GraphClientReceiveMessage type
# ------------------------------------------------------------------------------
@app.function_name(name="OnFlaggedEmail")
@app.connector_trigger(
    arg_name="emails",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnFlaggedEmailTriggerConfigName%",
)
def on_flagged_email(emails: list[office365.GraphClientReceiveMessage]) -> None:
    """Triggered when an email is flagged in Office 365."""
    logging.info("Received OnFlaggedEmail trigger (%d items)", len(emails))


# ------------------------------------------------------------------------------
# OnNewMentionMeEmail — GraphClientReceiveMessage type
# ------------------------------------------------------------------------------
@app.function_name(name="OnNewMentionMeEmail")
@app.connector_trigger(
    arg_name="emails",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnNewMentionMeEmailTriggerConfigName%",
)
def on_new_mention_me_email(emails: list[office365.GraphClientReceiveMessage]) -> None:
    """Triggered when a new email mentioning the current user arrives."""
    logging.info("Received OnNewMentionMeEmail trigger (%d items)", len(emails))


# ------------------------------------------------------------------------------
# OnNewCalendarEvent — GraphCalendarEventClientReceive type
# ------------------------------------------------------------------------------
@app.function_name(name="OnNewCalendarEvent")
@app.connector_trigger(
    arg_name="events",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnNewCalendarEventTriggerConfigName%",
)
def on_new_calendar_event(events: list[office365.GraphCalendarEventClientReceive]) -> None:
    """Triggered when a new calendar event is created in Office 365."""
    logging.info("Received OnNewCalendarEvent trigger (%d items)", len(events))


# ------------------------------------------------------------------------------
# OnUpcomingEvent — GraphCalendarEventClientReceive type
# ------------------------------------------------------------------------------
@app.function_name(name="OnUpcomingEvent")
@app.connector_trigger(
    arg_name="events",
    connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnUpcomingEventTriggerConfigName%",
)
def on_upcoming_event(events: list[office365.GraphCalendarEventClientReceive]) -> None:
    """Triggered when an upcoming calendar event is about to start."""
    logging.info("Received OnUpcomingEvent trigger (%d items)", len(events))


@app.function_name(name="OnCalendarUpdatedItems")
@app.connector_trigger(
    arg_name="events", connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnCalendarUpdatedItemsTriggerConfigName%",
)
def on_calendar_updated_items(events: list[office365.GraphCalendarEventClientReceive]) -> None:
    """Count modified calendar events without logging their content."""
    logging.info("Received OnCalendarUpdatedItems trigger (%d items)", len(events))


@app.function_name(name="OnSharedMailboxNewEmail")
@app.connector_trigger(
    arg_name="emails", connection="ConnectorNamespace",
    delivery_mode=func.DeliveryMode.POLL,
    trigger_config_name="%OnSharedMailboxNewEmailTriggerConfigName%",
)
def on_shared_mailbox_new_email(emails: list[office365.GraphClientReceiveMessage]) -> None:
    """Count shared messages when the optional listener is enabled."""
    logging.info("Received OnSharedMailboxNewEmail trigger (%d items)", len(emails))
