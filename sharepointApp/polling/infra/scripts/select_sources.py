"""Authorize SharePoint and select a site, library, and list before provisioning."""

import json
import shutil
import subprocess
import sys
from urllib.parse import parse_qsl, quote, urlsplit

from setup import CATALOG, authorize, cli, find_trigger, list_triggers, namespace_url, private_json, required


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


def query(outputs: dict, path: str) -> list:
    items = []
    queries = {}
    seen = set()
    while True:
        request = {"method": "GET", "path": path, "queries": queries}
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
            raise ValueError("SharePoint returned an invalid selector response.")
        status = str(response.get("statusCode"))
        if not (status.isdigit() and 200 <= int(status) < 300) and status not in ("OK", "Created", "Accepted"):
            raise RuntimeError(f"SharePoint selector request failed ({status}); check connection permissions.")
        body = response.get("body")
        if isinstance(body, str):
            body = json.loads(body)
        if not isinstance(body, dict) or not isinstance(body.get("value"), list):
            raise ValueError("SharePoint returned an invalid selector list.")
        items.extend(body["value"])
        next_link = body.get("nextLink") or body.get("@odata.nextLink")
        if not next_link:
            return items
        if not isinstance(next_link, str) or next_link in seen:
            raise ValueError("SharePoint returned an invalid or repeated continuation link.")
        seen.add(next_link)
        parsed = urlsplit(path + next_link if next_link.startswith("?") else next_link)
        if ((parsed.netloc and (parsed.scheme != "https" or parsed.username or parsed.password)) or
                (parsed.scheme and not parsed.netloc) or parsed.path.rstrip("/") != path.rstrip("/") or
                parsed.fragment):
            raise ValueError("SharePoint returned a continuation link outside the selected source.")
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if not pairs or len({key for key, _ in pairs}) != len(pairs):
            raise ValueError("SharePoint returned invalid continuation parameters.")
        queries = dict(pairs)


def choose(label: str, choices: list[tuple[str, str]]) -> str:
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


def select(outputs: dict, label: str, path: str, manual: str, default: str = "") -> str:
    items = query(outputs, path)
    choices = [(f"Enter a {manual} manually", "__manual__")]
    if default:
        choices.append(("Use the selected library", default))
    choices.extend(
        (item.get("DisplayName") or item["Name"], item["Name"])
        for item in items if isinstance(item, dict) and isinstance(item.get("Name"), str) and item["Name"].strip()
    )
    selected = choose(label, choices)
    return input(f"SharePoint {manual}: ").strip() if selected == "__manual__" else selected


def validate_site(value: str) -> None:
    validate("SHAREPOINT_SITE_URL", value)
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or
            parsed.query or parsed.fragment):
        raise ValueError("SHAREPOINT_SITE_URL must be an HTTPS site URL without credentials, query, or fragment.")


def main() -> None:
    outputs = cli("azd", "env", "get-values", "--output", "json")
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd environment outputs.")
    required(outputs, "AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName",
             "connectorNamespaceConnectionName", "functionAppName")
    cli("az", "extension", "show", "--name", "connector-namespace", "-o", "json")
    if not authorize(outputs, link_only=False):
        raise RuntimeError("SharePoint consent is required before creating Poll triggers.")
    collection = namespace_url(outputs)
    existing = list_triggers(collection)
    for item in CATALOG:
        find_trigger(existing, collection, item, outputs, "polling")
    site = outputs.get("SHAREPOINT_SITE_URL", "")
    if not site:
        site = select(outputs, "Sites", "/datasets", "site URL")
        validate_site(site)
        save("SHAREPOINT_SITE_URL", site)
    else:
        validate_site(site)
        print("Using SHAREPOINT_SITE_URL from the azd environment.")
    dataset = quote(quote(site.rstrip("/"), safe=""), safe="")
    library = outputs.get("SHAREPOINT_LIBRARY_NAME", "")
    if not library:
        library = select(outputs, "Libraries", f"/datasets/{dataset}/tablesfor/libraries", "library ID")
        save("SHAREPOINT_LIBRARY_NAME", library)
    else:
        validate("SHAREPOINT_LIBRARY_NAME", library)
        print("Using SHAREPOINT_LIBRARY_NAME from the azd environment.")
    if "SHAREPOINT_LIST_NAME" not in outputs:
        value = select(outputs, "Lists", f"/datasets/{dataset}/tables", "list ID", library)
        save("SHAREPOINT_LIST_NAME", value)
    elif outputs["SHAREPOINT_LIST_NAME"]:
        validate("SHAREPOINT_LIST_NAME", outputs["SHAREPOINT_LIST_NAME"])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, EOFError) as error:
        print(f"SharePoint setup failed: {error}", file=sys.stderr)
        sys.exit(1)
