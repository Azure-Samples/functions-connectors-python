"""Choose a Teams team and channel using the authorized connection."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import parse_qsl, quote, urlsplit

from trigger_inventory import verify_existing

OPERATIONS = {
    name: name for name in (
        "OnNewChannelMessage", "OnNewChannelMessageMentioningMe", "OnGroupMembershipAdd",
        "OnGroupMembershipRemoval", "WebhookChatMessageTrigger", "WebhookNewMessageTrigger",
        "WebhookAtMentionTrigger", "WebhookKeywordTrigger", "WebhookMessageReactionTrigger",
        "RecordingTrigger", "TranscriptTrigger",
    )
}


def command(program: str, *args: str) -> str:
    executable = shutil.which(program + ".cmd") if os.name == "nt" else None
    executable = executable or shutil.which(program)
    if not executable:
        raise RuntimeError(f"{program} is required.")
    result = subprocess.run([executable, *args], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"{program} failed with exit code {result.returncode}.")
    return result.stdout


def query(outputs: dict, path: str) -> list:
    items = []
    queries = {}
    seen = set()
    while True:
        request = {"method": "GET", "path": path, "queries": queries}
        descriptor, filename = tempfile.mkstemp(prefix="teams-selector-", suffix=".json")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(request, stream)
            raw = command(
                "az", "connector-namespace", "connection", "invoke",
                "--subscription", outputs["AZURE_SUBSCRIPTION_ID"], "-g", outputs["resourceGroupName"],
                "--namespace", outputs["connectorNamespaceName"],
                "--connection-name", outputs["connectorNamespaceConnectionName"],
                "--request", "@" + filename, "-o", "json",
            )
        finally:
            os.remove(filename)
        response = json.loads(raw).get("response")
        if not isinstance(response, dict):
            raise ValueError("Teams returned an invalid selector response.")
        status = str(response.get("statusCode"))
        if not (status.isdigit() and 200 <= int(status) < 300) and status not in ("OK", "Created", "Accepted"):
            raise RuntimeError(f"Teams selector request failed ({status}); check connection permissions.")
        body = response.get("body")
        if isinstance(body, str):
            body = json.loads(body)
        if not isinstance(body, dict) or not isinstance(body.get("value"), list):
            raise ValueError("Teams returned an invalid selector list.")
        items.extend(body["value"])
        next_link = body.get("@odata.nextLink") or body.get("nextLink")
        if not next_link:
            return items
        if not isinstance(next_link, str) or next_link in seen:
            raise ValueError("Teams returned an invalid or repeated continuation link.")
        seen.add(next_link)
        parsed = urlsplit(path + next_link if next_link.startswith("?") else next_link)
        if ((parsed.netloc and (parsed.scheme != "https" or parsed.netloc.lower() != "graph.microsoft.com")) or
                parsed.path.rstrip("/") != path.rstrip("/") or parsed.fragment or parsed.username or parsed.password):
            raise ValueError("Teams returned a continuation link outside the selected source.")
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if not pairs or len({key for key, _ in pairs}) != len(pairs):
            raise ValueError("Teams returned invalid continuation parameters.")
        queries = dict(pairs)


def choose(label: str, items: list) -> str:
    choices = [("Enter an ID manually", None)]
    choices.extend(
        (item.get("displayName") or item["id"], item["id"])
        for item in items if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
    )
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
                selected = shown[index - 1][1]
                return input(f"{label} ID: ").strip() if selected is None else selected
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


def valid(value: str, name: str) -> None:
    if (not isinstance(value, str) or not value.strip() or value != value.strip() or
            any(char in value for char in ('"', "\\", "\r", "\n"))):
        raise ValueError(f"{name} must be a nonempty connector-returned ID.")


def main() -> None:
    outputs = json.loads(command("azd", "env", "get-values", "--output", "json"))
    for name in ("AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName",
                 "connectorNamespaceConnectionName"):
        valid(outputs.get(name), name)
    verify_existing(outputs, "teams", "teams", OPERATIONS, command)
    group = outputs.get("TEAMS_GROUP_ID", "")
    if not group:
        group = choose("Teams", query(outputs, "/beta/me/joinedTeams"))
        valid(group, "TEAMS_GROUP_ID")
        command("azd", "env", "set", "TEAMS_GROUP_ID", group)
    else:
        valid(group, "TEAMS_GROUP_ID")
        print("Using TEAMS_GROUP_ID from the azd environment.")
    channel = outputs.get("TEAMS_CHANNEL_ID", "")
    if not channel:
        channel = choose("Channels", query(outputs, f"/beta/groups/{quote(group, safe='')}/channels"))
        valid(channel, "TEAMS_CHANNEL_ID")
        command("azd", "env", "set", "TEAMS_CHANNEL_ID", channel)
    else:
        valid(channel, "TEAMS_CHANNEL_ID")
        print("Using TEAMS_CHANNEL_ID from the azd environment.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, EOFError) as error:
        print(f"Teams setup failed: {error}", file=sys.stderr)
        sys.exit(1)
