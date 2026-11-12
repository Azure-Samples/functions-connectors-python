# Copyright (c) Microsoft Corporation.  All rights reserved.
"""Set up Salesforce sources after deployment; importing this module has no side effects."""

from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit

API_VERSION = "2026-05-01-preview"
OPERATIONS = {
    "OnSalesforceNewItems": "GetOnNewItems",
    "OnSalesforceUpdatedItems": "GetOnUpdatedItems",
}
PARAMETERS = {"table", "$filter", "$orderby", "$select"}
READ_ONLY = ("provisioningState", "pollingEndpoints")


def read_json(text: str) -> object:
    """Reject duplicate keys and non-JSON numbers without echoing input."""
    def pairs(items):
        result = {}
        for name, value in items:
            if name in result:
                raise ValueError("Duplicate JSON property.")
            result[name] = value
        return result

    def constant(value):
        raise ValueError("Non-finite JSON number.")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except ValueError:
        raise ValueError("Invalid JSON response or input.") from None


def cli(program: str, *arguments: str, interactive: bool = False) -> object:
    """Run a CLI without logging arguments, response bodies, or secrets."""
    executable = (shutil.which(program + ".cmd") if os.name == "nt" else None) or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is unavailable.")
    if interactive and not sys.stdin.isatty():
        raise ValueError("Authentication requires an interactive terminal; rerun the hook there.")
    result = subprocess.run(
        [executable, *arguments], check=False, timeout=660 if interactive else 120,
        **({} if interactive else {"capture_output": True, "text": True, "encoding": "utf-8"}),
    )
    if result.returncode:
        raise RuntimeError(f"'{program}' failed; command arguments and error bodies were not logged.")
    if interactive or not result.stdout.strip():
        return None
    return read_json(result.stdout)


@contextmanager
def private_directory(parent: Path | None = None):
    """Restrict a new staging directory before writing any request files."""
    with tempfile.TemporaryDirectory(prefix="salesforce-hook-", dir=parent) as directory:
        if os.name == "nt":
            executable = shutil.which("pwsh") or shutil.which("powershell")
            if not executable:
                raise RuntimeError("PowerShell is required to restrict Windows staging permissions.")
            script = r"""
$ErrorActionPreference = 'Stop'
$directory = $env:SALESFORCE_STAGING_DIRECTORY
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $directory /inheritance:r /grant:r "*${sid}:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Staging permission update failed.' }
$initial = Get-Acl -LiteralPath $directory
foreach ($rule in $initial.Access) {
    $otherSid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
    if ($rule.AccessControlType -eq 'Allow' -and $otherSid -ne $sid) {
        & icacls.exe $directory /remove:g "*$otherSid" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Staging grant removal failed.' }
    }
}
$acl = Get-Acl -LiteralPath $directory
if (-not $acl.AreAccessRulesProtected) { throw 'Staging inheritance is still enabled.' }
foreach ($rule in $acl.Access) {
    if ($rule.AccessControlType -eq 'Allow' -and
        $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -ne $sid) {
        throw 'Staging has another allowed principal.'
    }
}
"""
            result = subprocess.run(
                [executable, "-NoProfile", "-NonInteractive", "-Command", script],
                env={**os.environ, "SALESFORCE_STAGING_DIRECTORY": str(Path(directory).resolve())},
                capture_output=True, check=False, timeout=30,
            )
            if result.returncode:
                raise RuntimeError("Could not restrict Windows staging permissions; no request file was written.")
        else:
            os.chmod(directory, 0o700)
        yield Path(directory)


@contextmanager
def private_json(value: object):
    """Stage restricted JSON and remove it on success or failure."""
    with private_directory() as directory:
        path = directory / "request.json"
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        yield "@" + str(path)


def required(outputs: dict, *names: str) -> None:
    """Reject missing deployment context before resource writes."""
    for name in names:
        if not isinstance(outputs.get(name), str) or not outputs[name].strip():
            raise ValueError(f"Missing deployment output '{name}'. Run azd provision first.")


def context(outputs: dict) -> str:
    """Verify that the namespace ID agrees with the pinned deployment context."""
    required(outputs, "AZURE_SUBSCRIPTION_ID", "resourceGroupName", "functionAppName",
             "functionAppDefaultHostname", "connectorNamespaceName", "connectorNamespaceResourceId",
             "connectorNamespaceConnectionName")
    expected = (f"/subscriptions/{outputs['AZURE_SUBSCRIPTION_ID']}/resourceGroups/{outputs['resourceGroupName']}"
                f"/providers/Microsoft.Web/connectorGateways/{outputs['connectorNamespaceName']}")
    if outputs["connectorNamespaceResourceId"].lower() != expected.lower():
        raise ValueError("Namespace ID does not match the deployment subscription and resource names.")
    if any(not re.fullmatch(r"[A-Za-z0-9_-]+", outputs[name]) for name in (
        "AZURE_SUBSCRIPTION_ID", "resourceGroupName", "functionAppName", "connectorNamespaceName",
        "connectorNamespaceConnectionName",
    )):
        raise ValueError("Unsafe resource context.")
    hostname = outputs["functionAppDefaultHostname"]
    if not valid_hostname(hostname):
        raise ValueError("Invalid provisioned Function App hostname.")
    if not isinstance(outputs.get("salesforceAuthenticationParameterSetName"), str):
        raise ValueError("Authentication selector output is unavailable. Reprovision before setup.")
    return "https://management.azure.com" + expected


def rest(outputs: dict, method: str, url: str, body: object = None) -> object:
    """Pin every ARM request to the deployment subscription."""
    arguments = ["rest", "--method", method, "--url",
                 url if "?" in url else url + "?api-version=" + API_VERSION,
                 "--subscription", outputs["AZURE_SUBSCRIPTION_ID"], "-o", "json"]
    if body is None:
        return cli("az", *arguments)
    with private_json(body) as path:
        return cli("az", *arguments, "--body", path)


def authorize(outputs: dict, root: str) -> None:
    """Skip existing consent, or authenticate interactively and confirm Connected."""
    url = root + "/connections/" + quote(outputs["connectorNamespaceConnectionName"], safe="")

    def connected() -> bool:
        response = rest(outputs, "get", url)
        properties = response.get("properties") if isinstance(response, dict) else None
        if (not isinstance(properties, dict) or not isinstance(response.get("id"), str)
                or response["id"].lower() != urlsplit(url).path.lower()
                or properties.get("connectorName") != "salesforce"):
            raise ValueError("Salesforce connection readback does not match the deployment.")
        selector = outputs["salesforceAuthenticationParameterSetName"]
        parameter_set = properties.get("parameterValueSet")
        if selector and (not isinstance(parameter_set, dict) or parameter_set.get("name") != selector):
            raise ValueError("Actual connection authentication selector differs from the provisioned template.")
        status = properties.get("overallStatus")
        if not isinstance(status, str) or not status:
            raise ValueError("Connection status is unavailable.")
        return status.lower() == "connected"

    if connected():
        return
    cli("az", "connector-namespace", "connection", "authenticate", "-g", outputs["resourceGroupName"],
        "--namespace", outputs["connectorNamespaceName"], "--connection-name",
        outputs["connectorNamespaceConnectionName"], "--subscription", outputs["AZURE_SUBSCRIPTION_ID"],
        "--timeout", "300", "--no-access-policy", interactive=True)
    if not connected():
        raise ValueError("Salesforce connection is not Connected after authentication. Rerun after resolving consent.")


def validate_inputs(triggers: object) -> list[dict]:
    """Accept only reviewed event/function pairs and Swagger wire parameters."""
    if not isinstance(triggers, list) or not triggers:
        raise ValueError("Select at least one Salesforce trigger.")
    seen = set()
    for trigger in triggers:
        if not isinstance(trigger, dict) or set(trigger) != {"functionName", "operationName", "parameters"}:
            raise ValueError("Unexpected trigger input fields.")
        function = trigger["functionName"]
        if not isinstance(function, str) or function not in OPERATIONS or function in seen:
            raise ValueError("Unknown or duplicate Salesforce function.")
        seen.add(function)
        if trigger["operationName"] != OPERATIONS[function] or not isinstance(trigger["parameters"], list):
            raise ValueError("Trigger operation does not match its function.")
        names = set()
        for parameter in trigger["parameters"]:
            if not isinstance(parameter, dict) or set(parameter) != {"name", "value"}:
                raise ValueError("Unexpected parameter fields.")
            name, value = parameter["name"], parameter["value"]
            if not isinstance(name, str) or name not in PARAMETERS or name in names:
                raise ValueError("Unknown or duplicate wire parameter.")
            if (not isinstance(value, str) or not value.strip() or value != value.strip()
                    or re.search(r"<[^>]+>|REPLACE|PLACEHOLDER|YOUR[_ -]|CHANGEME", value, re.IGNORECASE)):
                raise ValueError("Supply real nonempty Salesforce values, not placeholders.")
            names.add(name)
        if "table" not in names:
            raise ValueError("Each selected event requires the Salesforce object identifier in 'table'.")
    return triggers


def collect_inputs(path: Path) -> list[dict]:
    """Read reviewed local JSON, or prompt for actual object IDs and optional queries."""
    if path.exists():
        return validate_inputs(read_json(path.read_text(encoding="utf-8")))
    if not sys.stdin.isatty():
        raise ValueError("Provide trigger-inputs.json or rerun setup in an interactive terminal.")
    triggers = []
    for function, operation in OPERATIONS.items():
        answer = input(f"Configure {function}? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            continue
        parameters = [{"name": "table", "value": input("Actual Salesforce Object Type identifier (GetTables Name): ").strip()}]
        for name in ("$filter", "$orderby", "$select"):
            value = input(f"Optional {name} (blank omits): ").strip()
            if value:
                parameters.append({"name": name, "value": value})
        triggers.append({"functionName": function, "operationName": operation, "parameters": parameters})
    return validate_inputs(triggers)


def list_triggers(outputs: dict, collection: str) -> list[dict]:
    """Follow strict same-collection HTTPS pagination, including empty first pages."""
    target = urlsplit(collection)
    visited, resources = set(), []
    url = collection + "?api-version=" + API_VERSION
    while url is not None:
        if not isinstance(url, str) or not url or re.search(r"[\s\\]", url):
            raise ValueError("Invalid trigger continuation URL.")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != target.netloc or parsed.username or parsed.password
                or parsed.path.lower() != target.path.lower() or parsed.fragment or url in visited):
            raise ValueError("Unsafe or repeated trigger continuation URL.")
        visited.add(url)
        page = rest(outputs, "get", url)
        if not isinstance(page, dict) or not isinstance(page.get("value"), list):
            raise ValueError("Invalid trigger inventory response.")
        if any(not isinstance(item, dict) for item in page["value"]):
            raise ValueError("Invalid trigger inventory resource.")
        resources.extend(page["value"])
        url = page.get("nextLink")
    return resources


def metadata(outputs: dict, function: str) -> dict[str, str]:
    """Record app ownership even for Poll delivery without a callback."""
    return {"destinationType": "functionApp", "functionAppName": outputs["functionAppName"],
            "functionAppResourceGroup": outputs["resourceGroupName"],
            "functionAppSubscriptionId": outputs["AZURE_SUBSCRIPTION_ID"], "functionName": function}


def trigger_name(outputs: dict, function: str) -> str:
    """Keep source names stable across reruns and both delivery modes."""
    return outputs["connectorNamespaceConnectionName"] + "-" + function.lower()


def owned(outputs: dict, collection: str, function: str, mode: str, resources: list[dict]) -> dict | None:
    """Reject duplicate IDs, foreign apps, wrong connections, operations and delivery modes."""
    name = trigger_name(outputs, function)
    expected_id = urlsplit(collection).path + "/" + name
    if any(not isinstance(item, dict) for item in resources):
        raise ValueError("Invalid trigger readback resource.")
    matches = [item for item in resources if str(item.get("name", "")).lower() == name.lower()
               or str(item.get("id", "")).lower() == expected_id.lower()]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("Duplicate sample trigger inventory entries.")
    item = matches[0]
    properties = item.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("Invalid existing trigger properties.")
    if not isinstance(properties.get("metadata"), dict):
        raise ValueError("Existing source has invalid ownership metadata.")
    parameters = properties.get("parameters")
    if (not isinstance(parameters, list) or any(
            not isinstance(parameter, dict) or not isinstance(parameter.get("name"), str)
            or "value" not in parameter for parameter in parameters)
            or len({parameter["name"] for parameter in parameters}) != len(parameters)):
        raise ValueError("Existing source has invalid parameters.")
    if mode == "webhook" and not isinstance(properties.get("notificationDetails"), dict):
        raise ValueError("Existing source has invalid notification details.")
    if "pollingEndpoints" in properties and not isinstance(properties["pollingEndpoints"], (dict, type(None))):
        raise ValueError("Existing source has invalid polling metadata.")
    modes = ("Poll",) if mode == "polling" else (None, "", "Webhook", "Push", "NotSpecified")
    if (str(item.get("id", "")).lower() != expected_id.lower() or item.get("name") != name
            or properties.get("operationName") != OPERATIONS[function]
            or properties.get("connectionDetails") != {"connectorName": "salesforce",
                                                       "connectionName": outputs["connectorNamespaceConnectionName"]}
            or properties.get("deliveryMode") not in modes
            or any(properties.get("metadata", {}).get(key) != value for key, value in metadata(outputs, function).items())):
        raise ValueError("Refusing to overwrite a trigger whose app, connection, operation or mode does not match.")
    return item


def writable(resource: dict | None) -> dict:
    """Preserve other writable properties while excluding server-generated fields."""
    properties = copy.deepcopy(resource["properties"]) if resource else {}
    for name in READ_ONLY:
        properties.pop(name, None)
    return properties


def valid_hostname(hostname: str) -> bool:
    """Accept DNS labels, not ambiguous origins or dot segments."""
    return isinstance(hostname, str) and len(hostname) <= 253 and "." in hostname and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in hostname.split("."))


def polling_endpoint(receive_uri: object, name: str) -> str:
    """Keep the HTTPS origin and gateway path; strip only a trailing /api suffix."""
    if not isinstance(receive_uri, str) or re.search(r"[\s\\]", receive_uri):
        raise ValueError("Polling receive URI is unavailable.")
    parsed = urlsplit(receive_uri)
    marker = "/triggerconfigs/" + name.lower() + "/"
    if (parsed.scheme != "https" or not parsed.hostname or not valid_hostname(parsed.hostname)
            or parsed.username or parsed.password
            or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("Invalid polling receive URI.")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("A service DNS hostname is required.")
    position = parsed.path.lower().find(marker)
    if position < 0 or parsed.path[position + len(marker):].lower() != "receive":
        raise ValueError("Receive URI does not identify the selected trigger.")
    base = parsed.path[:position].rstrip("/")
    if not re.fullmatch(r"/api|/(?:api/)?connectorGateways/[A-Za-z0-9_-]+(?:/api)?", base, re.IGNORECASE):
        raise ValueError("Receive URI has no valid Connector Namespace gateway path.")
    if base.lower().endswith("/api"):
        base = base[:-4]
    return "https://" + parsed.hostname.lower() + base


def ready(outputs: dict, collection: str, function: str, mode: str) -> dict:
    """Bound registration polling and refuse failed or incomplete source metadata."""
    url = collection + "/" + quote(trigger_name(outputs, function), safe="")
    for attempt in range(30):
        resource = rest(outputs, "get", url)
        resource = owned(outputs, collection, function, mode, [resource])
        if resource is None:
            raise ValueError("Trigger readback is missing.")
        properties = resource["properties"]
        state = properties.get("provisioningState")
        if state in ("Failed", "Canceled", "Cancelled"):
            raise ValueError("Salesforce source registration failed.")
        if state == "Succeeded":
            endpoints = properties.get("pollingEndpoints")
            if mode != "polling" or isinstance(endpoints, dict) and endpoints.get("receiveUri"):
                return resource
        if attempt < 29:
            time.sleep(2)
    raise TimeoutError("Salesforce source did not return ready registration metadata.")


def extension_key(outputs: dict) -> str:
    """Verify actual defaultHostName before reading the connector extension system key."""
    arguments = ("-g", outputs["resourceGroupName"], "-n", outputs["functionAppName"],
                 "--subscription", outputs["AZURE_SUBSCRIPTION_ID"], "-o", "json")
    app = cli("az", "functionapp", "show", *arguments)
    if not isinstance(app, dict) or app.get("defaultHostName") != outputs["functionAppDefaultHostname"]:
        raise ValueError("Actual Function App hostname differs from provisioned output.")
    for attempt in range(6):
        keys = cli("az", "functionapp", "keys", "list", *arguments)
        system_keys = keys.get("systemKeys") if isinstance(keys, dict) else None
        key = system_keys.get("connector_extension") if isinstance(system_keys, dict) else None
        if isinstance(key, str) and key.strip():
            return key
        if attempt < 5:
            time.sleep(2)
    raise ValueError("connector_extension system key is unavailable. Check the deployed host and rerun.")


def configure(outputs: dict, root: str, mode: str, triggers: list[dict]) -> dict[str, str]:
    """Preflight all sources before writes, preserve reruns, and disable deselections."""
    validate_inputs(triggers)
    if mode not in ("polling", "webhook") or root != context(outputs):
        raise ValueError("Setup mode or namespace differs from the deployment context.")
    collection = root + "/triggerConfigs"
    resources = list_triggers(outputs, collection)
    # Check every known source, including deselected functions, before any PUT.
    existing = {function: owned(outputs, collection, function, mode, resources) for function in OPERATIONS}
    selected = {trigger["functionName"]: trigger for trigger in triggers}
    key = extension_key(outputs) if mode == "webhook" else None
    settings = {}
    endpoint = None
    for function, operation in OPERATIONS.items():
        source = existing[function]
        properties = writable(source)
        settings[f"AzureWebJobs.{function}.Disabled"] = str(function not in selected).lower()
        name = trigger_name(outputs, function)
        if mode == "polling":
            settings[function + "TriggerConfigName"] = name
        if function not in selected:
            if source and properties.get("state") != "Disabled":
                properties["state"] = "Disabled"
                rest(outputs, "put", collection + "/" + quote(name, safe=""), {"properties": properties})
            continue
        properties.setdefault("type", "NotSpecified")
        properties.setdefault("description", "Salesforce " + operation + " -> " + function)
        properties.setdefault("metadata", {}).update(metadata(outputs, function))
        properties["metadata"].setdefault("recurrenceFrequency", "Minute")
        properties["metadata"].setdefault("recurrenceInterval", "5")
        properties.update(connectionDetails={"connectorName": "salesforce",
                                             "connectionName": outputs["connectorNamespaceConnectionName"]},
                          operationName=operation, parameters=selected[function]["parameters"], state="Enabled")
        if mode == "polling":
            properties["deliveryMode"] = "Poll"
        else:
            auth_query = {"type": "QueryString", "name": "code", "value": key}
            notification = properties.setdefault("notificationDetails", {})
            notification.update(callbackUrl="https://" + outputs["functionAppDefaultHostname"]
                                + "/runtime/webhooks/connector?functionName=" + function,
                                httpMethod="Post", authentication=auth_query)
        before = writable(source)
        # Parameter order has no wire meaning; keep an unchanged source untouched.
        if source and isinstance(before.get("parameters"), list):
            before["parameters"] = sorted(before["parameters"], key=lambda item: item["name"])
        compared = copy.deepcopy(properties)
        compared["parameters"] = sorted(compared["parameters"], key=lambda item: item["name"])
        if before != compared or source["properties"].get("provisioningState") in ("Failed", "Canceled", "Cancelled"):
            rest(outputs, "put", collection + "/" + quote(name, safe=""), {"properties": properties})
        registered = ready(outputs, collection, function, mode)
        if mode == "polling":
            current = polling_endpoint(registered["properties"]["pollingEndpoints"]["receiveUri"], name)
            if endpoint and endpoint != current:
                raise ValueError("Selected sources returned different polling gateways.")
            endpoint = current
    if mode == "polling":
        settings.update(ConnectorNamespace__credential="managedidentity", ConnectorNamespace__pollingEndpoint=endpoint)
    with private_json(settings) as path:
        cli("az", "functionapp", "config", "appsettings", "set", "-g", outputs["resourceGroupName"],
            "-n", outputs["functionAppName"], "--subscription", outputs["AZURE_SUBSCRIPTION_ID"],
            "--settings", path, "-o", "none")
    return settings


def write_local_settings(path: Path, cloud: dict[str, str], *, force: bool = False) -> bool:
    """Preserve existing bytes unless --force explicitly requests atomic replacement."""
    def check() -> bool:
        if (path.is_symlink() or getattr(path, "is_junction", lambda: False)()
                or (path.exists() and not path.is_file())):
            raise ValueError("Local settings must be a regular file, not a link or directory.")
        return path.exists()

    if check() and not force:
        return False
    values = {name: value for name, value in cloud.items() if name != "ConnectorNamespace__credential"}
    values.update(AzureWebJobsStorage="UseDevelopmentStorage=true", FUNCTIONS_WORKER_RUNTIME="python",
                  PYTHON_ISOLATE_WORKER_DEPENDENCIES="1")
    with private_directory(path.parent) as directory:
        temporary = directory / "local.settings.json"
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"IsEncrypted": False, "Values": values}, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        check()
        if force:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
        return True


def main(argv: list[str] | None = None) -> None:
    """Run the shared hook only on explicit invocation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("polling", "webhook"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--force", "--force-local-settings", action="store_true")
    options = parser.parse_args(argv)
    project = options.project.resolve()
    outputs = cli("azd", "env", "get-values", "--output", "json")
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd deployment outputs.")
    root = context(outputs)
    authorize(outputs, root)
    triggers = collect_inputs(options.inputs or project / "trigger-inputs.json")
    settings = configure(outputs, root, options.mode, triggers)
    changed = write_local_settings(project / "local.settings.json", settings, force=options.force)
    print("Salesforce setup complete. " + ("Created restricted local settings." if changed else "Existing local settings preserved."))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError, EOFError):
        print("Salesforce setup failed. Resolve connection, input or registration readiness and rerun; no secrets logged.", file=sys.stderr)
        sys.exit(1)