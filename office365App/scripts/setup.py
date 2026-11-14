# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Shared, standard-library-only Office365 deployment hooks; Azure calls are explicit.

Importing this module never reads credentials or calls Azure. Both shell entry
points use this implementation so JSON quoting and preservation rules agree.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit


OPERATIONS = {
    "OnNewEmail": "OnNewEmailV3",
    "OnFlaggedEmail": "OnFlaggedEmailV4",
    "OnNewMentionMeEmail": "OnNewMentionMeEmailV3",
    "OnNewCalendarEvent": "CalendarGetOnNewItemsV3",
    "OnUpcomingEvent": "OnUpcomingEventsV3",
    "OnCalendarUpdatedItems": "CalendarGetOnUpdatedItemsV3",
    "OnSharedMailboxNewEmail": "SharedMailboxOnNewEmailV2",
}
API_VERSION = "2026-05-01-preview"
SHARED_FUNCTION = "OnSharedMailboxNewEmail"


def cli(program: str, *arguments: str) -> object:
    """Run an authorized CLI command without echoing arguments or error bodies."""
    executable = shutil.which(program + ".cmd") if os.name == "nt" else None
    executable = executable or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is not installed.")
    result = subprocess.run(
        [executable, *arguments], capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"'{program}' failed; no settings or callback secrets were printed.")
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise RuntimeError(f"'{program}' did not return valid JSON.") from None


@contextmanager
def private_json(value: object):
    """Stage JSON in an owned private directory and remove it on every exit."""
    directory = tempfile.mkdtemp(prefix="office365-hook-")
    failed = False
    try:
        path = Path(directory) / "request.json"
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        yield "@" + str(path)
    except BaseException:
        failed = True
        raise
    finally:
        try:
            shutil.rmtree(directory)
        except OSError:
            if not failed:
                raise RuntimeError("Could not clean owned Office365 staging files.") from None
            print("Warning: staging cleanup failed; original error preserved.", file=sys.stderr)


def settings_file_exists(path: Path) -> bool:
    """Reject links, junctions and directories rather than following them."""
    if (path.is_symlink() or getattr(path, "is_junction", lambda: False)() or
            (path.exists() and not path.is_file())):
        raise ValueError("local.settings.json must be a regular file, not a link or directory.")
    return path.exists()


def write_local_settings(path: Path, values: dict[str, str], *, force: bool = False) -> bool:
    """Preserve existing bytes, or atomically install explicit secret-free values."""
    if settings_file_exists(path) and not force:
        print("Existing local.settings.json preserved byte-for-byte.")
        return False
    descriptor, temporary = tempfile.mkstemp(prefix=".local-settings-", suffix=".tmp", dir=path.parent)
    staging = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"IsEncrypted": False, "Values": values}, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if json.loads(staging.read_text(encoding="utf-8")) != {"IsEncrypted": False, "Values": values}:
            raise ValueError("Generated local settings failed validation.")
        settings_file_exists(path)
        if force:
            os.replace(staging, path)
        else:
            os.link(staging, path)
        print("Created ignored local settings for Python, Azurite and developer authentication.")
        return True
    finally:
        staging.unlink(missing_ok=True)


def required(outputs: dict, *names: str) -> None:
    """Reject absent azd outputs before any resource changes."""
    for name in names:
        if not isinstance(outputs.get(name), str) or not outputs[name].strip():
            raise ValueError(f"Missing azd output '{name}'. Run azd provision first.")


def local_values(outputs: dict, mode: str) -> dict[str, str]:
    """Build local-only settings; never copy cloud credentials or client IDs."""
    values = {
        "AzureWebJobsStorage": "UseDevelopmentStorage=true",
        "FUNCTIONS_WORKER_RUNTIME": "python",
        "PYTHON_ISOLATE_WORKER_DEPENDENCIES": "1",
        f"AzureWebJobs.{SHARED_FUNCTION}.Disabled": str(
            not bool(outputs.get("office365SharedMailboxAddress", "").strip())
        ).lower(),
    }
    if mode == "polling":
        required(outputs, "connectorPollingEndpoint")
        values["ConnectorNamespace__pollingEndpoint"] = outputs["connectorPollingEndpoint"]
        settings = outputs.get("triggerConfigSettings")
        if isinstance(settings, str):
            settings = json.loads(settings)
        if not isinstance(settings, dict):
            raise ValueError("Missing trigger configuration settings.")
        required(settings, *(name + "TriggerConfigName" for name in OPERATIONS))
        values.update({name + "TriggerConfigName": settings[name + "TriggerConfigName"] for name in OPERATIONS})
    return values


def namespace_url(outputs: dict) -> str:
    """Use encoded path segments within the selected subscription and namespace."""
    required(outputs, "AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName")
    segments = [quote(outputs[name], safe="") for name in (
        "AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName",
    )]
    return (f"https://management.azure.com/subscriptions/{segments[0]}/resourceGroups/{segments[1]}"
            f"/providers/Microsoft.Web/connectorGateways/{segments[2]}/triggerConfigs")


def list_triggers(collection: str) -> list[dict]:
    """Follow only same-collection ARM continuation URLs, including empty pages."""
    target = urlsplit(collection)
    visited = set()
    url = collection + "?api-version=" + API_VERSION
    resources = []
    while url:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != target.netloc or
                parsed.path.rstrip("/").lower() != target.path.lower() or
                parsed.fragment or url in visited):
            raise ValueError("Invalid or repeated trigger continuation URL.")
        visited.add(url)
        page = cli("az", "rest", "--method", "get", "--url", url, "-o", "json")
        if not isinstance(page, dict) or not isinstance(page.get("value"), list):
            raise ValueError("Invalid trigger list response.")
        resources.extend(page["value"])
        url = page.get("nextLink")
    return resources


def find_trigger(resources: list[dict], collection: str, name: str, operation: str,
                 outputs: dict, mode: str) -> dict | None:
    """Verify ownership before changing an existing sample subscription."""
    expected_id = urlsplit(collection).path + "/" + name
    matches = [item for item in resources if item.get("name", "").lower() == name.lower() or
               item.get("id", "").lower() == expected_id.lower()]
    if not matches:
        return None
    item = matches[0]
    properties = item.get("properties", {})
    connection = properties.get("connectionDetails", {})
    allowed_modes = ("Poll",) if mode == "polling" else (None, "", "Push", "NotSpecified")
    if (len(matches) != 1 or item.get("id", "").lower() != expected_id.lower() or
            item.get("name", "").lower() != name.lower() or
            properties.get("operationName") != operation or
            connection.get("connectionName") != outputs["connectorNamespaceConnectionName"] or
            connection.get("connectorName") != "office365" or
            properties.get("deliveryMode") not in allowed_modes):
        raise ValueError(f"Refusing to change '{name}': subscription ownership does not match.")
    return item


def put_properties(url: str, properties: dict) -> None:
    """Send JSON through a private file, never shell interpolation or command logs."""
    with private_json({"properties": properties}) as body:
        cli("az", "rest", "--method", "put", "--url", url, "--body", body, "-o", "none")


def disable_shared_poll(outputs: dict, collection: str, resources: list[dict]) -> None:
    """Change only state; preserve recurrence, metadata, parameters and large numbers."""
    if outputs.get("office365SharedMailboxAddress", "").strip():
        return
    settings = outputs["triggerConfigSettings"]
    if isinstance(settings, str):
        settings = json.loads(settings)
    name = settings[SHARED_FUNCTION + "TriggerConfigName"]
    resource = find_trigger(resources, collection, name, OPERATIONS[SHARED_FUNCTION], outputs, "polling")
    if resource is None:
        return
    url = collection + "/" + quote(name, safe="") + "?api-version=" + API_VERSION
    current = cli("az", "rest", "--method", "get", "--url", url, "-o", "json")
    find_trigger([current], collection, name, OPERATIONS[SHARED_FUNCTION], outputs, "polling")
    properties = copy.deepcopy(current["properties"])
    if properties.get("state") == "Disabled":
        return
    for read_only in ("provisioningState", "pollingEndpoints"):
        properties.pop(read_only, None)
    properties["state"] = "Disabled"
    put_properties(url, properties)


def trigger_parameters(name: str, outputs: dict) -> list[dict[str, str]]:
    """Use source-specific parameter names, without the old high-importance filter."""
    if name == SHARED_FUNCTION:
        return [{"name": "mailboxAddress", "value": outputs["office365SharedMailboxAddress"]},
                {"name": "folderId", "value": outputs.get("office365SharedMailboxFolderId", "Inbox")}]
    if name in ("OnNewCalendarEvent", "OnUpcomingEvent", "OnCalendarUpdatedItems"):
        return [{"name": "table", "value": outputs["office365CalendarId"]}]
    return [{"name": "folderPath", "value": outputs["office365MailFolder"]}]


def configure_webhooks(outputs: dict, collection: str, resources: list[dict],
                       callback: str | None, key: str | None) -> None:
    """Upsert callbacks using the extension system key, not function or host keys."""
    local_callback = callback is not None
    if callback:
        parsed = urlsplit(callback)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or
                parsed.query or parsed.fragment or parsed.path not in ("", "/") or not key):
            raise ValueError("Local callbacks require an HTTPS origin and a local connector extension key.")
    elif key:
        raise ValueError("A callback origin is required with a local connector extension key.")
    else:
        required(outputs, "functionAppName", "functionAppDefaultHostname")
        keys = cli("az", "functionapp", "keys", "list", "-g", outputs["resourceGroupName"],
                   "-n", outputs["functionAppName"], "-o", "json")
        key = keys.get("systemKeys", {}).get("connector_extension") if isinstance(keys, dict) else None
        if not key or not isinstance(key, str):
            raise ValueError("The connector_extension system key is unavailable. Deploy the app first.")
        callback = "https://" + outputs["functionAppDefaultHostname"]
    for function, operation in OPERATIONS.items():
        if function == SHARED_FUNCTION and not outputs.get("office365SharedMailboxAddress", "").strip():
            continue
        name = outputs["connectorNamespaceConnectionName"] + "-" + function.lower()
        existing = find_trigger(resources, collection, name, operation, outputs, "webhook")
        properties = copy.deepcopy(existing["properties"]) if existing else {}
        for read_only in ("provisioningState", "pollingEndpoints"):
            properties.pop(read_only, None)
        metadata = properties.setdefault("metadata", {})
        metadata.setdefault("recurrenceFrequency", "Minute")
        metadata.setdefault("recurrenceInterval", "5")
        for field in ("destinationType", "functionAppName", "functionAppResourceGroup",
                      "functionAppSubscriptionId", "functionName"):
            metadata.pop(field, None)
        if not local_callback:
            metadata.update(destinationType="functionApp", functionAppName=outputs["functionAppName"],
                            functionAppResourceGroup=outputs["resourceGroupName"],
                            functionAppSubscriptionId=outputs["AZURE_SUBSCRIPTION_ID"], functionName=function)
        properties.setdefault("type", "NotSpecified")
        properties.update(
            connectionDetails={"connectionName": outputs["connectorNamespaceConnectionName"], "connectorName": "office365"},
            operationName=operation, state=outputs["office365TriggerState"],
            parameters=trigger_parameters(function, outputs),
            notificationDetails={"callbackUrl": callback.rstrip("/") + "/runtime/webhooks/connector?functionName=" + function,
                                 "authentication": {"type": "QueryString", "name": "code", "value": key}},
            description="Office 365 " + function,
        )
        put_properties(collection + "/" + quote(name, safe="") + "?api-version=" + API_VERSION, properties)
        print(f"Configured {function} -> {operation}.")
    if not outputs.get("office365SharedMailboxAddress", "").strip():
        print("Shared mailbox listener disabled. Any prior webhook source must be disabled or deleted separately.")


def authorize(outputs: dict, *, link_only: bool) -> bool:
    """Return whether consent allows setup; link-only always defers writes."""
    arguments = ("-g", outputs["resourceGroupName"], "--namespace", outputs["connectorNamespaceName"])

    def status() -> str:
        connection = cli("az", "connector-namespace", "connection", "show", *arguments,
                         "-n", outputs["connectorNamespaceConnectionName"], "-o", "json")
        value = connection.get("properties", {}).get("overallStatus") if isinstance(connection, dict) else None
        if not isinstance(value, str) or not value:
            raise ValueError("Office365 connection status is unavailable.")
        return value

    if status() == "Connected":
        print("Office365 connection is already authorized; existing consent preserved.")
        return not link_only
    link = None
    with private_json([{"parameterName": "token", "redirectUrl": "https://connectors.azure.com"}]) as parameters:
        for attempt in range(5):
            try:
                response = cli("az", "connector-namespace", "connection", "list-consent-links", *arguments,
                               "--connection-name", outputs["connectorNamespaceConnectionName"],
                               "--parameters", parameters, "-o", "json")
            except RuntimeError:
                response = None
            if isinstance(response, dict):
                links = response.get("value", [])
                link = response.get("link") or (links[0].get("link") if links else None)
            if link:
                break
            if attempt < 4:
                time.sleep(5)
    if not isinstance(link, str) or urlsplit(link).scheme != "https":
        raise ValueError("Could not obtain an HTTPS Office365 consent link.")
    print("Authorize the Office365 connection with the mailbox account to monitor.")
    print("Consent URL: " + link)
    if link_only or outputs["office365TriggerState"] == "Disabled":
        return False
    try:
        webbrowser.open(link)
    except OSError:
        print("Open the consent URL in a browser.")
    deadline = time.monotonic() + 300
    while status() != "Connected":
        if time.monotonic() >= deadline:
            raise TimeoutError("Timed out waiting for Office365 OAuth consent.")
        time.sleep(3)
    return True


def main(argv: list[str] | None = None) -> None:
    """Run only when explicitly invoked by a delivery-mode hook."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("polling", "webhook"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--force-local-settings", action="store_true")
    parser.add_argument("--consent-link-only", action="store_true",
                        help="Show consent status or a link without opening a browser, waiting, or writing settings or triggers.")
    parser.add_argument("--callback-base-url")
    parser.add_argument("--connector-extension-key")
    options = parser.parse_args(argv)
    if options.mode == "polling" and (options.callback_base_url or options.connector_extension_key):
        raise ValueError("Polling does not use a callback or system key.")
    outputs = cli("azd", "env", "get-values", "--output", "json")
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd environment outputs.")
    required(outputs, "resourceGroupName", "connectorNamespaceName", "connectorNamespaceConnectionName",
             "office365TriggerState")
    if outputs["office365TriggerState"] not in ("Enabled", "Disabled"):
        raise ValueError("Invalid Office365 trigger state.")
    values = local_values(outputs, options.mode)
    if options.mode == "webhook":
        required(outputs, "office365MailFolder", "office365CalendarId")
    cli("az", "extension", "show", "--name", "connector-namespace", "-o", "json")
    collection = namespace_url(outputs)
    if not authorize(outputs, link_only=options.consent_link_only):
        print("Setup deferred; rerun the hook after consent without --consent-link-only.")
        return
    resources = list_triggers(collection)
    write_local_settings(options.project.resolve() / "local.settings.json", values, force=options.force_local_settings)
    if options.mode == "polling":
        disable_shared_poll(outputs, collection, resources)
    else:
        configure_webhooks(outputs, collection, resources, options.callback_base_url, options.connector_extension_key)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)