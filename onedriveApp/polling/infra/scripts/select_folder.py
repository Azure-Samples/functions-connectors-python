"""Interactively choose the OneDrive folder after consent and save ONEDRIVE_FOLDER_ID.

Skips the prompt when ONEDRIVE_FOLDER_ID is already set in the azd environment.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote

from trigger_inventory import verify_existing
from validate_folder import validate_folder_id

PAGE_SIZE = 25
OPERATIONS = {
    "OnOneDriveNewFile": "OnNewFilesV2",
    "OnOneDriveUpdatedFile": "OnUpdatedFilesV2",
    "OnOneDriveNewFileContent": "OnNewFileV2",
    "OnOneDriveUpdatedFileContent": "OnUpdatedFileV2",
}


def run(*args: str) -> str:
    executable = shutil.which(args[0])
    if not executable:
        raise RuntimeError(f"{args[0]} is required.")
    result = subprocess.run([executable, *args[1:]], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"'{args[0]} {args[1]}' failed; command details were not printed.")
    return result.stdout


def invoke(outputs: dict, request: dict) -> object:
    descriptor, request_file = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(request, stream)
        raw = run(
            "az", "connector-namespace", "connection", "invoke",
            "--subscription", outputs["AZURE_SUBSCRIPTION_ID"],
            "-g", outputs["resourceGroupName"],
            "--namespace", outputs["connectorNamespaceName"],
            "--connection-name", outputs["connectorNamespaceConnectionName"],
            "--request", f"@{request_file}", "-o", "json",
        )
    finally:
        os.remove(request_file)
    response = json.loads(raw).get("response", {})
    status = str(response.get("statusCode"))
    if not (status.isdigit() and 200 <= int(status) < 300) and status not in ("OK", "Created", "Accepted"):
        raise RuntimeError("OneDrive request failed; check the connection and folder permissions.")
    body = response.get("body")
    return json.loads(body) if isinstance(body, str) else body


def list_folders(outputs: dict, folder_id: str | None) -> list:
    path = f"/datasets/default/folders/{quote(folder_id, safe='')}" if folder_id else "/datasets/default/folders"
    body = invoke(outputs, {"method": "GET", "path": path})
    items = body if isinstance(body, list) else (body or {}).get("value")
    if not isinstance(items, list):
        raise RuntimeError("The OneDrive connector returned an invalid folder listing.")
    return [item for item in items
            if isinstance(item, dict) and item.get("IsFolder") is True
            and isinstance(item.get("Id"), str) and item["Id"] not in ("", "root")]


def choose(label: str, choices: list[tuple[str, object]]) -> object:
    filtered = choices
    show_all = False
    while True:
        shown = filtered if show_all else filtered[:PAGE_SIZE]
        print(f"{label} (showing {len(shown)} of {len(filtered)}):")
        for index, (title, _) in enumerate(shown, 1):
            print(f"  [{index}] {title}")
        answer = input("Select by number, enter text to filter, or * to show all: ").strip()
        if not answer:
            raise RuntimeError("A selection is required. Set ONEDRIVE_FOLDER_ID to run without a prompt.")
        if answer.isdigit():
            if 1 <= int(answer) <= len(shown):
                return shown[int(answer) - 1][1]
            print(f"Enter a number from 1 to {len(shown)}.")
            continue
        matches = choices if answer == "*" else [c for c in choices if answer.lower() in c[0].lower()]
        if matches:
            filtered = matches
            show_all = answer == "*"
        else:
            print("No matching choices.")


def root_folder_id(outputs: dict) -> str:
    body = invoke(outputs, {"method": "GET", "path": "/datasets/default/GetFileByPath", "queries": {"path": "/"}})
    folder_id = body.get("Id") if isinstance(body, dict) else None
    if not isinstance(folder_id, str):
        raise RuntimeError("Could not resolve the OneDrive root folder ID.")
    return folder_id


def select_folder(outputs: dict) -> str:
    stack: list[dict] = []
    while True:
        current = stack[-1] if stack else None
        where = "/" + "/".join(item.get("Name", "") for item in stack)
        choices: list[tuple[str, object]] = [(f"Use this folder ({where})", "select")]
        if current:
            choices.append((".. (parent folder)", "up"))
        choices += [(f"-> {folder.get('Name') or folder['Id']}", folder)
                    for folder in list_folders(outputs, current["Id"] if current else None)]
        choices.append(("Enter a folder ID manually", "manual"))
        selected = choose(f"OneDrive folder {where}", choices)
        if selected == "select":
            return current["Id"] if current else root_folder_id(outputs)
        if selected == "manual":
            return input("OneDrive folder ID: ").strip()
        if selected == "up":
            stack.pop()
        else:
            stack.append(selected)


def main() -> None:
    outputs = json.loads(run("azd", "env", "get-values", "--output", "json"))
    for key in ("AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName",
                "connectorNamespaceConnectionName"):
        if not outputs.get(key):
            raise RuntimeError(f"Missing azd output {key}. Run azd provision base first.")
    verify_existing(outputs, "onedrive", "onedriveforbusiness", OPERATIONS, run)
    existing = outputs.get("ONEDRIVE_FOLDER_ID", "")
    if existing:
        validate_folder_id(existing)
        print("Using ONEDRIVE_FOLDER_ID from the azd environment.")
        return
    folder_id = select_folder(outputs)
    validate_folder_id(folder_id)
    run("azd", "env", "set", "ONEDRIVE_FOLDER_ID", folder_id)
    print("Saved ONEDRIVE_FOLDER_ID to the azd environment.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
