# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import azurefunctions.extensions.connectors.office365 as office365
import logging
from typing import List

app = func.FunctionApp()


# ------------------------------------------------------------------------------
# OnNewEmail — ClientReceiveMessage type
# ------------------------------------------------------------------------------
@app.function_name(name="OnNewEmail")
@app.connector_trigger(arg_name="emails")
def on_new_email(emails: List[office365.ClientReceiveMessage]) -> None:
    """Triggered when a new email arrives in Office 365."""
    logging.info("OnNewEmail trigger received.")

    for email in emails:
        logging.info(f"Subject: '{email.subject}'.")
        logging.info(f"From: '{email.from_}'.")
        logging.info(f"Importance: '{email.importance}'.")
        logging.info(f"Has attachments: '{email.has_attachments}'.")

    logging.info(f"Batch contains '{len(emails)}' email(s).")


# ------------------------------------------------------------------------------
# OnFlaggedEmail — GraphClientReceiveMessage type
# ------------------------------------------------------------------------------
@app.function_name(name="OnFlaggedEmail")
@app.connector_trigger(arg_name="emails")
def on_flagged_email(emails: List[office365.GraphClientReceiveMessage]) -> None:
    """Triggered when an email is flagged in Office 365."""
    logging.info("OnFlaggedEmail trigger received.")

    for email in emails:
        logging.info(f"Subject: '{email.subject}'.")
        logging.info(f"From: '{email.from_}'.")
        logging.info(f"Importance: '{email.importance}'.")


# ------------------------------------------------------------------------------
# OnNewMentionMeEmail — GraphClientReceiveMessage type
# ------------------------------------------------------------------------------
@app.function_name(name="OnNewMentionMeEmail")
@app.connector_trigger(arg_name="emails")
def on_new_mention_me_email(emails: List[office365.GraphClientReceiveMessage]) -> None:
    """Triggered when a new email mentioning the current user arrives."""
    logging.info("OnNewMentionMeEmail trigger received.")

    for email in emails:
        logging.info(f"Subject: '{email.subject}'.")
        logging.info(f"From: '{email.from_}'.")


# ------------------------------------------------------------------------------
# OnNewCalendarEvent — GraphCalendarEventClientReceive type
# ------------------------------------------------------------------------------
@app.function_name(name="OnNewCalendarEvent")
@app.connector_trigger(arg_name="events")
def on_new_calendar_event(events: List[office365.GraphCalendarEventClientReceive]) -> None:
    """Triggered when a new calendar event is created in Office 365."""
    logging.info("OnNewCalendarEvent trigger received.")

    for event in events:
        logging.info(f"Subject: '{event.subject}'.")
        logging.info(f"Organizer: '{event.organizer}'.")
        logging.info(f"Start: '{event.start}'.")
        logging.info(f"End: '{event.end}'.")

    logging.info(f"Batch contains '{len(events)}' event(s).")


# ------------------------------------------------------------------------------
# OnUpcomingEvent — GraphCalendarEventClientReceive type
# ------------------------------------------------------------------------------
@app.function_name(name="OnUpcomingEvent")
@app.connector_trigger(arg_name="events")
def on_upcoming_event(events: List[office365.GraphCalendarEventClientReceive]) -> None:
    """Triggered when an upcoming calendar event is about to start."""
    logging.info("OnUpcomingEvent trigger received.")

    for event in events:
        logging.info(f"Subject: '{event.subject}'.")
        logging.info(f"Start: '{event.start}'.")
