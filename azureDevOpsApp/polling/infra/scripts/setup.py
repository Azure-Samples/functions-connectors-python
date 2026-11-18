# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Mode-local Azure DevOps hooks. Importing this module never calls Azure."""

from __future__ import annotations

import argparse
import base64
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
from urllib.parse import quote, unquote, urlsplit

from trigger_inputs import choose_from_terminal, collect_trigger_inputs, make_picker, parameters_for

API_VERSION = "2026-05-01-preview"
CONNECTOR = "visualstudioteamservices"
OPERATIONS = {
    "OnAzureDevOpsBuildCompleted": "OnBuildCompleted",
    "OnAzureDevOpsGitPullClosed": "OnGitPullClosed",
    "OnAzureDevOpsGitPullCreated": "OnGitPullCreated",
    "OnAzureDevOpsGitPush": "OnGitPush",
    "OnAzureDevOpsTfvcCheckIn": "OnTfvcCheckIn",
    "OnAzureDevOpsWorkItemAssigned": "OnWorkItemAssignedV2",
    "OnAzureDevOpsWorkItemClosed": "OnWorkItemClosedV2",
    "OnAzureDevOpsWorkItemCreated": "OnWorkItemCreatedV2",
    "OnAzureDevOpsWorkItemUpdated": "OnWorkItemUpdatedV2",
}
READ_ONLY = {"provisioningState", "pollingEndpoints"}
PENDING = {"accepted", "creating", "updating", "running"}
FAILED = {"failed", "canceled", "cancelled"}


def cli(program: str, arguments: list[str], *, interactive: bool = False) -> object:
    """Keep secrets out of logs and Windows command-shell expansion."""
    executable = (shutil.which(program + ".cmd") if os.name == "nt" else None) or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is not installed.")
    command = [executable]
    if Path(executable).suffix.lower() in {".cmd", ".bat"}:
        interpreter = Path(executable).parent.parent / "python.exe"
        if program != "az" or not interpreter.is_file():
            raise RuntimeError("Use the Azure CLI MSI and a native azd executable.")
        command = [str(interpreter), "-IBm", "azure.cli"]
    result = subprocess.run([*command, *arguments], capture_output=not interactive,
                            text=True, encoding="utf-8", timeout=660 if interactive else 120, check=False)
    if result.returncode:
        raise RuntimeError(f"'{program}' failed. Resolve the CLI error and rerun the hook.")
    return None if interactive or not result.stdout.strip() else json.loads(result.stdout)


def protect_path(path: Path) -> None:
    """Replace the DACL with a protected current-token-only grant, including inheritance."""
    if os.name != "nt":
        os.chmod(path, 0o700 if path.is_dir() else 0o600)
        return
    import ctypes
    import ctypes.wintypes

    wintypes = ctypes.wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    security.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    security.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    security.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    security.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    security.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    token, sid_text, descriptor = wintypes.HANDLE(), wintypes.LPWSTR(), ctypes.c_void_p()
    try:
        if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise RuntimeError("Cannot obtain the current identity for private files.")
        size = wintypes.DWORD()
        security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not size.value:
            raise RuntimeError("Cannot read the current token.")
        user = ctypes.create_string_buffer(size.value)
        if (not security.GetTokenInformation(token, 1, user, size, ctypes.byref(size))
                or not security.ConvertSidToStringSidW(ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p)).contents.value, ctypes.byref(sid_text))):
            raise RuntimeError("Cannot read the current user SID.")
        inheritance = "OICI" if path.is_dir() else ""
        if (not security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                f"D:P(A;{inheritance};FA;;;{sid_text.value})", 1, ctypes.byref(descriptor), None)
                or not security.SetFileSecurityW(str(path), 0x80000004, descriptor)):
            raise RuntimeError("Cannot restrict private files to the current user.")
    finally:
        if descriptor.value:
            kernel.LocalFree(descriptor)
        if sid_text:
            kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        if token.value:
            kernel.CloseHandle(token)


@contextmanager
def private_json(value: object):
    """Remove private request bodies even when a command fails."""
    with tempfile.TemporaryDirectory(prefix="azuredevops-setup-") as directory:
        protect_path(Path(directory))
        path = Path(directory) / "request.json"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream)
        yield "@" + str(path)


def dns_hostname(value: object) -> str:
    """Reject addresses, credentials and malformed DNS labels."""
    if (not isinstance(value, str) or len(value) > 253 or "." not in value
            or any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label) for label in value.split("."))):
        raise ValueError("Invalid service DNS hostname.")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value.lower()
    raise ValueError("Service hostname must not be an IP address.")


def https_uri(value: object):
    """Require an HTTPS DNS origin with no credentials, fragment or alternate port."""
    if not isinstance(value, str) or any(ord(character) <= 32 for character in value) or "\\" in value:
        raise ValueError("Invalid service HTTPS URI.")
    parsed = urlsplit(value)
    if (parsed.scheme.lower() != "https" or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443) or parsed.fragment):
        raise ValueError("Unsafe service HTTPS URI origin.")
    dns_hostname(parsed.hostname)
    return parsed


def context(outputs: dict, mode: str) -> dict:
    """Validate foundation identity; polling does not require an app to exist yet."""
    required = ("resourceGroupName", "functionAppName", "connectorNamespaceName", "connectorNamespaceResourceId",
                "connectorNamespaceConnectionName", "CONNECTOR_NAMESPACE_LOCATION", "deliveryMode")
    if any(not isinstance(outputs.get(key), str) or not outputs[key] for key in required):
        raise ValueError("Missing deployment outputs. Provision this mode's foundation first.")
    match = re.fullmatch(r"/subscriptions/([\w-]+)/resourceGroups/([\w.-]+)/providers/Microsoft.Web/connectorGateways/([\w-]+)",
                         outputs["connectorNamespaceResourceId"], re.IGNORECASE)
    if (not match or match[2].lower() != outputs["resourceGroupName"].lower()
            or match[3].lower() != outputs["connectorNamespaceName"].lower()
            or outputs["deliveryMode"] != mode
            or not re.fullmatch(r"[a-z0-9-]+-entra", outputs["connectorNamespaceConnectionName"])
            or not re.fullmatch(r"[\w-]+", outputs["functionAppName"])
            or outputs.get("AZURE_SUBSCRIPTION_ID", match[1]).lower() != match[1].lower()):
        raise ValueError("Deployment identity does not match this mode's Entra connection.")
    if mode == "webhook":
        dns_hostname(outputs.get("FUNCTION_APP_HOSTNAME"))
    root = "https://management.azure.com" + outputs["connectorNamespaceResourceId"]
    return {"subscription": match[1], "root": root, "collection": root + "/triggerConfigs"}


def rest(run, ctx: dict, method: str, url: str, body: object = None) -> dict:
    """Pin ARM calls to the selected subscription and stage bodies privately."""
    arguments = ["rest", "--method", method, "--url", url if "?" in url else url + "?api-version=" + API_VERSION,
                 "--subscription", ctx["subscription"], "-o", "json"]
    if body is None:
        result = run("az", arguments)
    else:
        with private_json(body) as path:
            result = run("az", arguments + ["--body", path])
    if not isinstance(result, dict):
        raise ValueError("Invalid ARM response.")
    return result


def authorize(run, ctx: dict, outputs: dict, *, wait=time.sleep) -> dict:
    """Check EntraOAuth on every read; finish consent before creating any source."""
    url = ctx["root"] + "/connections/" + outputs["connectorNamespaceConnectionName"]
    for attempt in range(30):
        connection = rest(run, ctx, "GET", url)
        properties = connection.get("properties", {})
        if properties.get("parameterValueSet", {}).get("name") != "EntraOAuth":
            raise ValueError("EntraOAuth is required; legacy connections cannot migrate in place.")
        state = str(properties.get("provisioningState", "")).lower()
        if state in FAILED:
            raise ValueError("Connection provisioning failed.")
        if state not in PENDING:
            break
        if attempt == 29:
            raise TimeoutError("Connection provisioning timed out.")
        wait(2)
    if str(properties.get("overallStatus", "")).lower() != "connected":
        run("az", ["connector-namespace", "connection", "authenticate", "-g", outputs["resourceGroupName"],
                   "--namespace", outputs["connectorNamespaceName"], "--connection-name", outputs["connectorNamespaceConnectionName"],
                   "--subscription", ctx["subscription"], "--timeout", "300", "--no-access-policy"], interactive=True)
        connection = rest(run, ctx, "GET", url)
        properties = connection.get("properties", {})
        if (properties.get("parameterValueSet", {}).get("name") != "EntraOAuth"
                or str(properties.get("overallStatus", "")).lower() != "connected"):
            raise ValueError("Connection must be Connected with EntraOAuth after consent.")
    return connection


def validate_selection(selected: object) -> None:
    """Validate the nine-event inventory and distinct string wire keys."""
    if not isinstance(selected, list) or not selected:
        raise ValueError("Select at least one source.")
    functions = set()
    for trigger in selected:
        if (not isinstance(trigger, dict) or set(trigger) != {"functionName", "operationName", "parameters"}
                or not isinstance(trigger["functionName"], str) or trigger["functionName"] not in OPERATIONS
                or trigger["functionName"] in functions or trigger["operationName"] != OPERATIONS[trigger["functionName"]]
                or not isinstance(trigger["parameters"], list)):
            raise ValueError("Use distinct functions and their exact operation names.")
        functions.add(trigger["functionName"])
        values = {}
        for item in trigger["parameters"]:
            if (not isinstance(item, dict) or set(item) != {"name", "value"} or not isinstance(item["name"], str)
                    or not item["name"] or item["name"] in values or not isinstance(item["value"], str)):
                raise ValueError("Parameters need distinct wire names and string values.")
            values[item["name"]] = item["value"]


def validate_inputs(selected: object, swagger: dict) -> dict:
    """Check all inputs against live string schemas before any configuration writes."""
    validate_selection(selected)
    result = {}
    for trigger in selected:
        schemas = parameters_for(swagger, trigger["operationName"])
        for schema in schemas:
            if (schema.get("in") not in {"path", "query"} or schema.get("type") != "string"
                    or not isinstance(schema.get("name"), str)
                    or any(type(schema[field]) is not int or schema[field] < 0 for field in ("minLength", "maxLength") if field in schema)
                    or "enum" in schema and not isinstance(schema["enum"], list)):
                raise ValueError("Unsupported connector string schema; no inputs will be guessed.")
            if "pattern" in schema:
                try:
                    re.compile(schema["pattern"])
                except (TypeError, re.error):
                    raise ValueError("Unsupported connector parameter pattern; no sources were changed.") from None
        expected = {schema["name"]: schema for schema in schemas}
        values = {item["name"]: item["value"] for item in trigger["parameters"]}
        if set(values) - set(expected) or any(schema.get("required") and schema["name"] not in values for schema in schemas):
            raise ValueError("Unknown wire key or missing required connector input.")
        for name, value in values.items():
            schema = expected[name]
            if (schema.get("required") and not value.strip() or len(value) < schema.get("minLength", 0)
                    or len(value) > schema.get("maxLength", sys.maxsize)
                    or "enum" in schema and value not in schema["enum"]
                    or "pattern" in schema and not re.search(schema["pattern"], value)):
                raise ValueError("Input does not satisfy the exported connector schema.")
        result[trigger["functionName"]] = trigger["parameters"]
    return result


def list_triggers(run, ctx: dict) -> list[dict]:
    """Follow bounded same-collection pagination, including empty pages."""
    target = urlsplit(ctx["collection"])
    url, resources, visited = ctx["collection"] + "?api-version=" + API_VERSION, [], set()
    while url:
        parsed = https_uri(url)
        identity = (parsed.hostname.lower(), parsed.path.lower(), parsed.query)
        if (parsed.hostname.lower() != target.hostname.lower() or parsed.path.lower() != target.path.lower()
                or identity in visited or len(visited) >= 100):
            raise ValueError("Unsafe, repeated or excessive trigger continuation URL.")
        visited.add(identity)
        response = rest(run, ctx, "GET", url)
        if not isinstance(response.get("value"), list) or any(not isinstance(item, dict)
                or not isinstance(item.get("id"), str) or not isinstance(item.get("name"), str) for item in response["value"]):
            raise ValueError("Invalid trigger inventory.")
        resources.extend(response["value"])
        url = response.get("nextLink")
    return resources


def metadata(outputs: dict, ctx: dict, function: str) -> dict:
    """Record the future or existing app's exact owner identity."""
    return {"destinationType": "functionApp", "functionAppSubscriptionId": ctx["subscription"],
            "functionAppResourceGroup": outputs["resourceGroupName"], "functionAppName": outputs["functionAppName"], "functionName": function}


def owned(resource: dict, ctx: dict, outputs: dict, function: str, name: str, mode: str) -> None:
    """Refuse writes unless identity, operation, connection, delivery and app all agree."""
    properties = resource.get("properties", {})
    if (str(resource.get("id", "")).lower() != (urlsplit(ctx["collection"]).path + "/" + name).lower()
            or str(resource.get("name", "")).lower() != name.lower()
            or properties.get("operationName") != OPERATIONS[function]
            or properties.get("connectionDetails") != {"connectorName": CONNECTOR, "connectionName": outputs["connectorNamespaceConnectionName"]}
            or properties.get("deliveryMode", "Webhook") != ("Poll" if mode == "polling" else "Webhook")
            or any(properties.get("metadata", {}).get(key) != value for key, value in metadata(outputs, ctx, function).items())):
        raise ValueError(f"Refusing to overwrite unowned or other-mode source '{name}'.")


def poll_endpoint(uri: object, name: str) -> str:
    """Use only the service's exact receive path; never call the returned URL."""
    parsed = https_uri(uri)
    match = re.fullmatch(r"(/api(?:/connectorGateways/[^/]+)?)/triggerconfigs/([^/]+)/receive", parsed.path, re.IGNORECASE)
    if (parsed.query or not match or unquote(match[2]).lower() != name.lower()
            or any(part in {".", ".."} for part in unquote(match[1]).split("/")) or "%" in match[1]):
        raise ValueError("Polling receive URI does not match this source.")
    return "https://" + parsed.hostname.lower() + ("" if match[1].lower() == "/api" else match[1])


def wait_ready(run, ctx: dict, url: str, resource: dict, *, require_receive: bool, wait=time.sleep) -> dict:
    """Bound source provisioning and receive-URI readiness."""
    for attempt in range(30):
        properties = resource.get("properties", {})
        state = str(properties.get("provisioningState") or "").lower()
        if state in FAILED:
            raise ValueError("Source registration failed.")
        if properties and state in {"", "succeeded"} and (not require_receive or properties.get("pollingEndpoints", {}).get("receiveUri")):
            return resource
        if attempt < 29:
            wait(2)
            resource = rest(run, ctx, "GET", url)
    raise TimeoutError("Source registration or receive URI timed out.")


def write_local(project: Path, values: dict, *, force: bool) -> None:
    """Preserve existing bytes by default, or atomically merge explicit local values."""
    destination = project / "local.settings.json"
    if destination.is_symlink() or getattr(destination, "is_junction", lambda: False)():
        raise ValueError("Local settings must not be a link.")
    if destination.exists() and not force:
        print("Existing local.settings.json preserved; review worker isolation before local testing.")
        return
    document = json.loads((destination if destination.exists() else project / "local.settings.example.json").read_text(encoding="utf-8"))
    if not isinstance(document.get("Values"), dict) or document.get("IsEncrypted") is not False:
        raise ValueError("Local settings must have unencrypted Values.")
    document["Values"].update(values, PYTHON_ISOLATE_WORKER_DEPENDENCIES="1")
    for key in ("ConnectorNamespace__credential", "AzureDevOpsConnection__credential", "VstsConnection__credential"):
        document["Values"].pop(key, None)
    descriptor, temporary = tempfile.mkstemp(prefix=".azuredevops-settings-", dir=project)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            protect_path(Path(temporary))
            json.dump(document, stream, indent=2)
            stream.write("\n")
        if force:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def setup(outputs: dict, selected: object, mode: str, project: Path, *, run=cli, wait=time.sleep,
          force_local: bool = False, prompt=input) -> None:
    """Consent, validate and preflight ownership; polling saves selected sources for the Bicep triggers layer."""
    ctx = context(outputs, mode)
    if selected is not None:
        validate_selection(selected)
    connection = authorize(run, ctx, outputs, wait=wait)
    exported = rest(run, ctx, "GET", "https://management.azure.com/subscriptions/" + ctx["subscription"]
                    + "/providers/Microsoft.Web/locations/" + quote(outputs["CONNECTOR_NAMESPACE_LOCATION"], safe="")
                    + "/managedApis/" + CONNECTOR + "?api-version=2016-06-01&export=true")
    swagger = exported.get("properties", {}).get("apiDefinitions", {}).get("value", exported)
    if isinstance(swagger, str):
        swagger = json.loads(swagger)
    if selected is None:
        connection_url = ctx["root"] + "/connections/" + quote(outputs["connectorNamespaceConnectionName"], safe="")
        invoke = make_picker(swagger, lambda body: rest(run, ctx, "POST", connection_url + "/dynamicInvoke", body))
        selected = collect_trigger_inputs(
            swagger, OPERATIONS, invoke, choose=choose_from_terminal(prompt), prompt=prompt,
            optional_filters=mode == "polling", skip_unavailable=mode == "webhook",
        )
    selections = validate_inputs(selected, swagger)
    key, runtime = None, connection.get("properties", {}).get("connectionRuntimeUrl")
    if mode == "webhook":
        https_uri(runtime)
        app = rest(run, ctx, "GET", "https://management.azure.com/subscriptions/" + ctx["subscription"]
                   + "/resourceGroups/" + outputs["resourceGroupName"] + "/providers/Microsoft.Web/sites/" + outputs["functionAppName"])
        if dns_hostname(app.get("properties", {}).get("defaultHostName")) != dns_hostname(outputs["FUNCTION_APP_HOSTNAME"]):
            raise ValueError("Actual app hostname disagrees with deployment output.")
        for attempt in range(30):
            try:
                keys = run("az", ["functionapp", "keys", "list", "-g", outputs["resourceGroupName"], "-n", outputs["functionAppName"],
                                  "--subscription", ctx["subscription"], "-o", "json"])
                key = keys.get("systemKeys", {}).get("connector_extension") if isinstance(keys, dict) else None
            except RuntimeError:
                key = None
            if isinstance(key, str) and key:
                break
            if attempt < 29:
                wait(2)
        if not isinstance(key, str) or not key:
            raise ValueError("No connector_extension system key; check host startup.")
    inventory, plan, existing_endpoint = list_triggers(run, ctx), [], None
    for function in OPERATIONS:
        name = outputs["connectorNamespaceConnectionName"] + "-" + function.lower()
        url = ctx["collection"] + "/" + name
        matches = [item for item in inventory if item["name"].lower() == name.lower() or item["id"].lower() == urlsplit(url).path.lower()]
        if len(matches) > 1:
            raise ValueError("Duplicate source inventory entries.")
        resource = rest(run, ctx, "GET", url) if matches else None
        if resource:
            resource = wait_ready(run, ctx, url, resource, require_receive=False, wait=wait)
            owned(resource, ctx, outputs, function, name, mode)
            if mode == "polling" and resource["properties"].get("pollingEndpoints", {}).get("receiveUri"):
                received = poll_endpoint(resource["properties"]["pollingEndpoints"]["receiveUri"], name)
                if existing_endpoint and existing_endpoint != received:
                    raise ValueError("Existing polling endpoints disagree.")
                existing_endpoint = received
        plan.append((function, name, url, resource))
    setting = "POLLING_TRIGGER_INPUTS" if mode == "polling" else "AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS"
    run("azd", ["env", "set", setting, base64.b64encode(json.dumps(selected).encode()).decode()])
    settings_arguments = ["functionapp", "config", "appsettings", "set", "-g", outputs["resourceGroupName"],
                          "-n", outputs["functionAppName"], "--subscription", ctx["subscription"], "-o", "none"]
    if mode == "webhook":
        with private_json({"AzureWebJobs." + function + ".Disabled": "true" for function in OPERATIONS}) as path:
            run("az", settings_arguments + ["--settings", path])
    settings, trigger_plan = {}, []
    for function, name, url, resource in plan:
        active = function in selections
        settings["AzureWebJobs." + function + ".Disabled"] = str(not active).lower()
        if mode == "polling":
            settings[function + "TriggerConfigName"] = name
        if not active:
            if resource and resource["properties"].get("state") != "Disabled":
                properties = {field: copy.deepcopy(value) for field, value in resource["properties"].items() if field not in READ_ONLY}
                properties["state"] = "Disabled"
                disabled = wait_ready(run, ctx, url, rest(run, ctx, "PUT", url, {"properties": properties}), require_receive=False, wait=wait)
                owned(disabled, ctx, outputs, function, name, mode)
                if disabled["properties"].get("state") != "Disabled":
                    raise ValueError("Deselected source was not disabled.")
            continue
        previous = {field: copy.deepcopy(value) for field, value in (resource or {}).get("properties", {}).items() if field not in READ_ONLY}
        properties = copy.deepcopy(previous)
        properties.update(connectionDetails={"connectorName": CONNECTOR, "connectionName": outputs["connectorNamespaceConnectionName"]},
                          operationName=OPERATIONS[function], parameters=selections[function], state="Enabled")
        properties.setdefault("metadata", {}).update(metadata(outputs, ctx, function))
        properties.setdefault("type", "NotSpecified")
        properties.setdefault("description", "Azure DevOps " + function)
        if mode == "polling":
            properties["deliveryMode"] = "Poll"
            properties.pop("notificationDetails", None)
            trigger_plan.append({"name": name, "properties": properties})
            print(f"Planned {function} ({mode}).")
            continue
        notification = properties.setdefault("notificationDetails", {})
        notification.update(callbackUrl="https://" + outputs["FUNCTION_APP_HOSTNAME"] + "/runtime/webhooks/connector?functionName=" + function, httpMethod="Post")
        notification.setdefault("authentication", {}).update(type="QueryString", name="code", value=key)
        ordered = lambda values: sorted(values, key=lambda item: item["name"])
        unchanged = bool(resource) and {**previous, "parameters": ordered(previous.get("parameters", []))} == {**properties, "parameters": ordered(properties["parameters"])}
        created = resource if unchanged else rest(run, ctx, "PUT", url, {"properties": properties})
        created = wait_ready(run, ctx, url, created, require_receive=False, wait=wait)
        owned(created, ctx, outputs, function, name, mode)
        if created["properties"].get("state") != "Enabled":
            raise ValueError("Selected source was not enabled.")
        print(f"Configured {function} ({mode}).")
    if mode == "polling":
        document = {"selected": trigger_plan, "settings": settings}
        run("azd", ["env", "set", "POLLING_TRIGGER_PLAN", base64.b64encode(json.dumps(document).encode()).decode()])
    else:
        with private_json({**settings, "AzureDevOpsConnection": runtime}) as path:
            run("az", settings_arguments + ["--settings", path])
        write_local(project, {**settings, "AzureDevOpsConnection": runtime}, force=force_local)
    print("Review old connections and source subscriptions manually. No unowned sources were deleted.")


def detect_app(outputs: dict, *, run=cli) -> None:
    """Fail closed on inventory errors; never mistake an authorization failure for absence."""
    subscription = outputs["AZURE_SUBSCRIPTION_ID"]
    group = outputs.get("resourceGroupName") or "rg-" + outputs["AZURE_ENV_NAME"]
    exists = run("az", ["group", "exists", "-n", group, "--subscription", subscription, "-o", "json"])
    if type(exists) is not bool:
        raise ValueError("Invalid resource group existence response.")
    names = run("az", ["functionapp", "list", "-g", group, "--subscription", subscription, "-o", "json"]) if exists else []
    if not isinstance(names, list) or any(not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in names):
        raise ValueError("Invalid Function App inventory.")
    expected = outputs.get("functionAppName")
    matches = [item for item in names if item["name"].lower() == expected.lower()] if expected else [
        item for item in names if item.get("tags", {}).get("azd-env-name") == outputs["AZURE_ENV_NAME"]
        and item.get("tags", {}).get("azd-service-name") == "function-app"]
    if len(matches) > 1:
        raise ValueError("Ambiguous Function App inventory.")
    run("azd", ["env", "set", "AZURE_DEVOPS_FUNCTION_APP_EXISTS", str(bool(matches)).lower()])


def main(argv: list[str] | None = None) -> None:
    """Run one mode-local hook; polling registration precedes app infrastructure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("polling", "webhook"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--phase", choices=("register", "prepare-app", "local"), default="register")
    parser.add_argument("--force-local-settings", action="store_true")
    parser.add_argument("--check-inputs", action="store_true")
    options = parser.parse_args(argv)
    project = options.project.resolve()
    path = options.inputs or project / "trigger-inputs.json"
    selected = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    if selected is not None or options.check_inputs:
        validate_selection(selected)
    if options.check_inputs:
        return
    outputs = cli("azd", ["env", "get-values", "--output", "json"])
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd outputs.")
    setting = "POLLING_TRIGGER_INPUTS" if options.mode == "polling" else "AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS"
    if options.phase == "register" and selected is None and outputs.get(setting):
        try:
            selected = json.loads(base64.b64decode(outputs[setting], validate=True))
            validate_selection(selected)
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid saved trigger selections. Clear {setting} and rerun setup.") from error
    if options.phase == "prepare-app":
        detect_app(outputs)
    elif options.phase == "local":
        context(outputs, options.mode)
        settings = json.loads(base64.b64decode(outputs["triggerConfigSettingsEncoded"], validate=True))
        write_local(project, {**settings, "ConnectorNamespace__pollingEndpoint": outputs["connectorPollingEndpoint"]}, force=options.force_local_settings)
    else:
        setup(outputs, selected, options.mode, project, force_local=options.force_local_settings)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, EOFError, re.error, subprocess.SubprocessError) as error:
        detail = f": {error}" if isinstance(error, (ValueError, RuntimeError)) and str(error) else "."
        print(f"Azure DevOps setup failed{detail}", file=sys.stderr)
        sys.exit(1)