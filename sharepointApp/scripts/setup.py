# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""SharePoint hooks shared by PowerShell and Bash; importing never calls Azure."""

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


API_VERSION = "2026-05-01-preview"
CATALOG = json.loads((Path(__file__).resolve().parents[1] / "polling/infra/triggers.json").read_text())
OPERATIONS = {item["functionName"]: item["operationName"] for item in CATALOG}


def cli(program: str, *arguments: str) -> object:
    """Run JSON commands without exposing arguments, bodies, or stderr secrets."""
    executable = shutil.which(program + ".cmd") if os.name == "nt" else None
    executable = executable or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is not installed.")
    result = subprocess.run([executable, *arguments], capture_output=True, text=True,
                            encoding="utf-8", check=False)
    if result.returncode:
        raise RuntimeError(f"'{program}' failed; command details were not printed.")
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise RuntimeError(f"'{program}' did not return valid JSON.") from None


@contextmanager
def private_json(value: object):
    """Remove owned private JSON staging on success and failure alike."""
    directory = tempfile.mkdtemp(prefix="sharepoint-hook-")
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
                raise RuntimeError("Could not clean owned SharePoint staging files.") from None
            print("Warning: staging cleanup failed; original error preserved.", file=sys.stderr)


def settings_file_exists(path: Path) -> bool:
    """Reject directories, symbolic links, and junctions before any write."""
    if (path.is_symlink() or getattr(path, "is_junction", lambda: False)() or
            (path.exists() and not path.is_file())):
        raise ValueError("local.settings.json must be a regular file.")
    return path.exists()


def write_local_settings(path: Path, values: dict[str, str], *, force: bool = False) -> bool:
    """Preserve existing bytes unless forced; atomically install private settings."""
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
        if json.loads(staging.read_text(encoding="utf-8"))["Values"] != values:
            raise ValueError("Generated local settings failed validation.")
        settings_file_exists(path)
        if force:
            os.replace(staging, path)
        else:
            os.link(staging, path)
        return True
    finally:
        staging.unlink(missing_ok=True)


def required(outputs: dict, *names: str) -> None:
    """Require nonempty deployment outputs before changing resources."""
    for name in names:
        if not isinstance(outputs.get(name), str) or not outputs[name].strip():
            raise ValueError(f"Missing azd output '{name}'. Run azd provision first.")


def decoded_output(outputs: dict, name: str, expected: type):
    """Accept structured azd outputs as JSON strings or decoded values."""
    value = outputs.get(name)
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, expected):
        raise ValueError(f"Invalid azd output '{name}'.")
    return value


def trigger_name(function: str, outputs: dict, mode: str) -> str:
    """Keep the existing Python Poll and webhook logical resource names."""
    prefix = "sharepoint" if mode == "polling" else outputs["connectorNamespaceConnectionName"]
    return prefix + "-" + function.lower()


def definitions(outputs: dict) -> list[dict]:
    """Validate the complete source inventory, selection flags, and SDK parameters."""
    items = decoded_output(outputs, "triggerDefinitions", list)
    if len(items) != 10 or {item.get("functionName") for item in items} != set(OPERATIONS):
        raise ValueError("Expected all ten SharePoint trigger definitions.")
    for item in items:
        function = item["functionName"]
        catalog = next(entry for entry in CATALOG if entry["functionName"] == function)
        if item.get("operationName") != OPERATIONS[function] or type(item.get("enabled")) is not bool:
            raise ValueError("Invalid SharePoint operation or selection flag.")
        if catalog["group"] == "standard" and not item["enabled"]:
            raise ValueError("All five standard SharePoint events must be selected.")
        parameters = item.get("parameters")
        if not isinstance(parameters, list) or not all(isinstance(parameter, dict) for parameter in parameters):
            raise ValueError("Invalid SharePoint parameters.")
        values = {parameter.get("name"): parameter.get("value") for parameter in parameters}
        expected = {"dataset", "table"}
        if catalog["folder"] and "folderPath" in values:
            expected.add("folderPath")
        if catalog["group"] == "form":
            expected.add("form")
        if catalog["group"] == "digest":
            expected.update(("update", "add", "runSchedule"))
        if len(values) != len(parameters) or set(values) != expected:
            raise ValueError("Unexpected or missing SharePoint parameter names.")
        required(values, "dataset", "table")
        if item["enabled"] and catalog["group"] == "form":
            required(values, "form")
        if catalog["group"] == "digest":
            if (values["runSchedule"] not in ("", "*", "0", "1", "2", "3", "4", "5", "6") or
                    values["update"] is not True or values["add"] is not True or
                    (item["enabled"] and values["runSchedule"] == "")):
                raise ValueError("Invalid SharePoint digest schedule or flags.")
    return items


def local_values(outputs: dict, mode: str) -> dict[str, str]:
    """Use Azurite and developer credentials, never cloud client IDs or secrets."""
    items = definitions(outputs)
    settings = decoded_output(outputs, "triggerConfigSettings", dict)
    values = {"AzureWebJobsStorage": "UseDevelopmentStorage=true", "FUNCTIONS_WORKER_RUNTIME": "python",
              "PYTHON_ISOLATE_WORKER_DEPENDENCIES": "1"}
    for item in items:
        function = item["functionName"]
        disabled = f"AzureWebJobs.{function}.Disabled"
        if settings.get(disabled) != str(not item["enabled"]).lower():
            raise ValueError("Function disabled flag does not match source selection.")
        values[disabled] = settings[disabled]
        if mode == "polling":
            name = function + "TriggerConfigName"
            if settings.get(name) != trigger_name(function, outputs, mode):
                raise ValueError("Trigger configuration name does not match the sample.")
            values[name] = settings[name]
    if mode == "polling":
        required(outputs, "connectorPollingEndpoint")
        values["ConnectorNamespace__pollingEndpoint"] = outputs["connectorPollingEndpoint"]
    return values


def namespace_url(outputs: dict) -> str:
    """Pin all writes to the selected subscription, resource group, and namespace."""
    required(outputs, "AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName")
    subscription, group, namespace = [quote(outputs[name], safe="") for name in
                                     ("AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName")]
    return (f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{group}"
            f"/providers/Microsoft.Web/connectorGateways/{namespace}/triggerConfigs")


def list_triggers(collection: str) -> list[dict]:
    """Follow same-collection continuation URLs, even after an empty page."""
    target = urlsplit(collection)
    visited = set()
    url = collection + "?api-version=" + API_VERSION
    resources = []
    while url:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != target.netloc or
                parsed.path.rstrip("/").lower() != target.path.lower() or parsed.fragment or url in visited):
            raise ValueError("Invalid or repeated trigger continuation URL.")
        visited.add(url)
        page = cli("az", "rest", "--method", "get", "--url", url, "-o", "json")
        if not isinstance(page, dict) or not isinstance(page.get("value"), list):
            raise ValueError("Invalid trigger list response.")
        resources.extend(page["value"])
        url = page.get("nextLink")
    return resources


def find_trigger(resources: list[dict], collection: str, item: dict, outputs: dict, mode: str) -> dict | None:
    """Reject ambiguous, foreign-scope, wrong-connection, or wrong-mode resources."""
    name = trigger_name(item["functionName"], outputs, mode)
    expected_id = urlsplit(collection).path + "/" + name
    matches = [resource for resource in resources if resource.get("name", "").lower() == name.lower() or
               resource.get("id", "").lower() == expected_id.lower()]
    if not matches:
        return None
    resource = matches[0]
    properties = resource.get("properties", {})
    connection = properties.get("connectionDetails", {})
    modes = ("Poll",) if mode == "polling" else (None, "", "Push", "NotSpecified")
    if (len(matches) != 1 or resource.get("id", "").lower() != expected_id.lower() or
            resource.get("name", "").lower() != name.lower() or
            properties.get("operationName") != item["operationName"] or
            connection.get("connectionName") != outputs["connectorNamespaceConnectionName"] or
            connection.get("connectorName") != "sharepointonline" or properties.get("deliveryMode") not in modes):
        raise ValueError(f"Refusing to change '{name}': subscription ownership does not match.")
    return resource


def put_properties(url: str, properties: dict) -> None:
    """Write only properties, using private JSON rather than command-line secrets."""
    with private_json({"properties": properties}) as body:
        cli("az", "rest", "--method", "put", "--url", url, "--body", body, "-o", "none")


def callback_details(outputs: dict, callback: str | None, key: str | None) -> tuple[str, str, bool]:
    """Use the real deployed hostname or an explicit HTTPS local origin and key."""
    local = callback is not None
    if local:
        parsed = urlsplit(callback)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or
                parsed.path not in ("", "/") or parsed.query or parsed.fragment or not key):
            raise ValueError("Local callbacks require an HTTPS origin and connector extension key.")
    elif key:
        raise ValueError("A callback origin is required with a local connector extension key.")
    else:
        required(outputs, "functionAppName", "functionAppDefaultHostname")
        callback = "https://" + outputs["functionAppDefaultHostname"]
        parsed = urlsplit(callback)
        if not parsed.hostname or parsed.netloc != outputs["functionAppDefaultHostname"] or parsed.path:
            raise ValueError("Invalid deployed Function App hostname.")
        response = cli("az", "functionapp", "keys", "list", "-g", outputs["resourceGroupName"],
                       "-n", outputs["functionAppName"], "-o", "json")
        key = response.get("systemKeys", {}).get("connector_extension") if isinstance(response, dict) else None
        if not isinstance(key, str) or not key:
            raise ValueError("The connector_extension system key is unavailable. Deploy the app first.")
    return callback.rstrip("/"), key, local


def configure_triggers(outputs: dict, mode: str, collection: str, resources: list[dict],
                       callback: str | None = None, key: str | None = None) -> None:
    """Upsert selected webhooks; stop unselected sources in either delivery mode."""
    items = definitions(outputs)
    existing = {item["functionName"]: find_trigger(resources, collection, item, outputs, mode) for item in items}
    if mode == "webhook":
        callback, key, local = callback_details(outputs, callback, key)
    for item in items:
        function = item["functionName"]
        resource = existing[function]
        if mode == "polling" and item["enabled"]:
            continue
        if not item["enabled"] and resource is None:
            continue
        name = trigger_name(function, outputs, mode)
        url = collection + "/" + quote(name, safe="") + "?api-version=" + API_VERSION
        if resource:
            current = cli("az", "rest", "--method", "get", "--url", url, "-o", "json")
            if find_trigger([current], collection, item, outputs, mode) is None:
                raise ValueError("Trigger disappeared before update.")
            properties = copy.deepcopy(current["properties"])
        else:
            properties = {}
        for field in ("pollingEndpoints", "provisioningState"):
            properties.pop(field, None)
        if not item["enabled"]:
            if properties.get("state") == "Disabled":
                continue
            properties["state"] = "Disabled"
        else:
            metadata = properties.setdefault("metadata", {})
            metadata.setdefault("recurrenceFrequency", "Minute")
            metadata.setdefault("recurrenceInterval", "5")
            for field in ("destinationType", "functionAppName", "functionAppResourceGroup", "functionAppSubscriptionId", "functionName"):
                metadata.pop(field, None)
            if not local:
                metadata.update(destinationType="functionApp", functionAppName=outputs["functionAppName"],
                                functionAppResourceGroup=outputs["resourceGroupName"],
                                functionAppSubscriptionId=outputs["AZURE_SUBSCRIPTION_ID"], functionName=function)
            properties.setdefault("type", "NotSpecified")
            properties.update(connectionDetails={"connectionName": outputs["connectorNamespaceConnectionName"],
                                                 "connectorName": "sharepointonline"},
                              operationName=item["operationName"], state="Enabled", parameters=item["parameters"],
                              description=item["description"], notificationDetails={
                                  "callbackUrl": callback + "/runtime/webhooks/connector?functionName=" + function,
                                  "authentication": {"type": "QueryString", "name": "code", "value": key}})
        put_properties(url, properties)


def authorize(outputs: dict, *, link_only: bool) -> bool:
    """Return whether consent allows setup; link-only always defers writes."""
    arguments = ("-g", outputs["resourceGroupName"], "--namespace", outputs["connectorNamespaceName"])

    def status() -> str:
        response = cli("az", "connector-namespace", "connection", "show", *arguments,
                       "-n", outputs["connectorNamespaceConnectionName"], "-o", "json")
        value = response.get("properties", {}).get("overallStatus") if isinstance(response, dict) else None
        if not isinstance(value, str) or not value:
            raise ValueError("SharePoint connection status is unavailable.")
        return value

    if status() == "Connected":
        print("SharePoint connection is already authorized; existing consent preserved.")
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
        raise ValueError("Could not obtain an HTTPS SharePoint consent link.")
    print("Authorize with an account that can access the monitored site and library.")
    print("Consent URL: " + link)
    if link_only:
        return False
    try:
        webbrowser.open(link)
    except OSError:
        print("Open the consent URL in a browser.")
    deadline = time.monotonic() + 300
    while status() != "Connected":
        if time.monotonic() >= deadline:
            raise TimeoutError("Timed out waiting for SharePoint OAuth consent.")
        time.sleep(3)
    return True


def main(argv: list[str] | None = None) -> None:
    """Run explicit delivery hooks only; tests replace every CLI boundary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("polling", "webhook"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--force-local-settings", action="store_true")
    parser.add_argument("--local-settings-only", action="store_true")
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
    required(outputs, "resourceGroupName", "connectorNamespaceName", "connectorNamespaceConnectionName")
    values = local_values(outputs, options.mode)
    if options.local_settings_only:
        if options.consent_link_only:
            parser.error("--local-settings-only cannot be combined with --consent-link-only.")
        write_local_settings(options.project.resolve() / "local.settings.json", values, force=options.force_local_settings)
        return
    cli("az", "extension", "show", "--name", "connector-namespace", "-o", "json")
    collection = namespace_url(outputs)
    if not authorize(outputs, link_only=options.consent_link_only):
        print("Setup deferred; rerun the hook after consent without --consent-link-only.")
        return
    resources = list_triggers(collection)
    write_local_settings(options.project.resolve() / "local.settings.json", values, force=options.force_local_settings)
    configure_triggers(outputs, options.mode, collection, resources, options.callback_base_url, options.connector_extension_key)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)