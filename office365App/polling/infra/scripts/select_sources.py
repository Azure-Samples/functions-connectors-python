"""Authorize Office 365 and select mailbox and calendar inputs before provisioning."""

import json
import shutil
import subprocess
import sys

from setup import OPERATIONS, authorize, cli, find_trigger, list_triggers, namespace_url, private_json, required

PAGE_SIZE = 100


def validate(name: str, value: str) -> None:
    if (not isinstance(value, str) or not value.strip() or value != value.strip() or
            any(char in value for char in ('"', "\\", "\r", "\n"))):
        raise ValueError(f"{name} must be a nonempty connector-returned value.")


def save(name: str, value: str) -> None:
    validate(name, value)
    executable = shutil.which("azd")
    if not executable:
        raise RuntimeError("The Azure Developer CLI is required.")
    result = subprocess.run([executable, "env", "set", name, value], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"Could not save {name} in the azd environment.")


def query(outputs: dict, path: str, queries: dict) -> list:
    items = []
    seen_pages = set()
    skip = 0
    while True:
        request = {"method": "GET", "path": path, "queries": {**queries, "top": PAGE_SIZE, "skip": skip}}
        with private_json(request) as body:
            response = cli(
                "az", "connector-namespace", "connection", "invoke",
                "--subscription", outputs["AZURE_SUBSCRIPTION_ID"],
                "-g", outputs["resourceGroupName"], "--namespace", outputs["connectorNamespaceName"],
                "--connection-name", outputs["connectorNamespaceConnectionName"],
                "--request", body, "-o", "json",
            )
        response = response.get("response") if isinstance(response, dict) else None
        if not isinstance(response, dict):
            raise ValueError("Office 365 returned an invalid selector response.")
        status = str(response.get("statusCode"))
        if not (status.isdigit() and 200 <= int(status) < 300) and status not in ("OK", "Created", "Accepted"):
            raise RuntimeError(f"Office 365 selector request failed ({status}); check connection permissions.")
        body = response.get("body")
        if isinstance(body, str):
            body = json.loads(body)
        page = body.get("value") if isinstance(body, dict) else None
        if not isinstance(page, list):
            raise ValueError("Office 365 returned an invalid selector list.")
        fingerprint = json.dumps(page, sort_keys=True, ensure_ascii=False)
        if page and fingerprint in seen_pages:
            raise RuntimeError("Office 365 repeated a selector page; cannot enumerate all choices safely.")
        seen_pages.add(fingerprint)
        items.extend(page)
        more = body.get("nextLink") or body.get("@odata.nextLink")
        if more and not page:
            raise RuntimeError("Office 365 returned an empty selector page with a continuation.")
        if not more and len(page) < PAGE_SIZE:
            return items
        skip += len(page)


def choose(label: str, choices: list[tuple[str, object]]) -> object:
    if not choices:
        raise ValueError(f"No {label} choices were returned.")
    filtered = choices
    show_all = False
    while True:
        shown = filtered if show_all else filtered[:25]
        print(f"{label} (showing {len(shown)} of {len(filtered)}):")
        for index, (title, _) in enumerate(shown, 1):
            print(f"  [{index}] {title}")
        answer = input("Select by number, enter text to filter, or * to show all: ").strip()
        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(shown):
                return shown[index - 1][1]
            print(f"Enter a number from 1 to {len(shown)}.")
        elif answer:
            matches = choices if answer == "*" else [item for item in choices if answer.lower() in item[0].lower()]
            if matches:
                filtered = matches
                show_all = answer == "*"
            else:
                print("No matching choices.")
        else:
            raise ValueError(f"A {label} selection is required.")


def folder(outputs: dict, mailbox: str = "") -> str:
    parents = []
    while True:
        current = parents[-1] if parents else None
        path = "/OnFilePickerBrowse" if current else "/OnFilePickerOpen"
        queries = {"operation": "MailFolders"}
        if mailbox:
            queries["mailboxAddress"] = mailbox
        if current:
            queries["id"] = current["Id"]
        folders = query(outputs, path, queries)
        folders = [item for item in folders if isinstance(item, dict) and item.get("IsFolder") is True
                   and isinstance(item.get("Id"), str) and item["Id"].strip()]
        choices = [("Enter a folder ID manually", "manual")]
        if current:
            choices.extend([(f"Use {current.get('DisplayName') or current['Id']}", "select"),
                            ("Go to the parent folder", "up")])
        else:
            choices.append(("Use Inbox", "inbox"))
        choices.extend((f"Open {item.get('DisplayName') or item['Id']}", item) for item in folders)
        selected = choose("Mail folders", choices)
        if selected == "manual":
            return input("Connector-returned folder ID: ").strip()
        if selected == "inbox":
            return "Inbox"
        if selected == "select":
            return current["Id"]
        if selected == "up":
            parents.pop()
        else:
            parents.append(selected)


def calendar(outputs: dict) -> str:
    calendars = query(outputs, "/codeless/v1.0/me/calendars", {})
    choices = [("Enter a calendar ID manually", "manual")]
    choices.extend(
        (item.get("name") or item["id"], item["id"])
        for item in calendars if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
    )
    selected = choose("Calendars", choices)
    return input("Connector-returned calendar ID: ").strip() if selected == "manual" else selected


def main() -> None:
    outputs = cli("azd", "env", "get-values", "--output", "json")
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd environment outputs.")
    required(outputs, "AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName",
             "connectorNamespaceConnectionName")
    cli("az", "extension", "show", "--name", "connector-namespace", "-o", "json")
    if not authorize(outputs, link_only=False):
        raise RuntimeError("Office 365 consent is required before creating Poll triggers.")
    collection = namespace_url(outputs)
    existing = list_triggers(collection)
    for function, operation in OPERATIONS.items():
        find_trigger(existing, collection, "office365-" + function.lower(), operation, outputs, "polling")
    for setting, selector in (("OFFICE365_MAIL_FOLDER", folder), ("OFFICE365_CALENDAR_ID", calendar)):
        value = outputs.get(setting)
        if value:
            validate(setting, value)
            print(f"Using {setting} from the azd environment.")
        else:
            value = selector(outputs)
            save(setting, value)
    mailbox = outputs.get("OFFICE365_SHARED_MAILBOX_ADDRESS", "")
    if mailbox:
        validate("OFFICE365_SHARED_MAILBOX_ADDRESS", mailbox)
        shared_folder = outputs.get("OFFICE365_SHARED_MAILBOX_FOLDER_ID", "")
        if shared_folder:
            validate("OFFICE365_SHARED_MAILBOX_FOLDER_ID", shared_folder)
        else:
            save("OFFICE365_SHARED_MAILBOX_FOLDER_ID", folder(outputs, mailbox))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, EOFError) as error:
        print(f"Office 365 setup failed: {error}", file=sys.stderr)
        sys.exit(1)
