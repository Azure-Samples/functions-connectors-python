# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Configure reviewed Azure DevOps sources after deployment, without logging secrets."""

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
from urllib.parse import quote, unquote, urlsplit

API_VERSION = "2026-05-01-preview"
CONNECTOR = "visualstudioteamservices"
OPERATIONS = {
    "OnVstsBuildCompleted": "OnBuildCompleted",
    "OnVstsGitPullClosed": "OnGitPullClosed",
    "OnVstsGitPullCreated": "OnGitPullCreated",
    "OnVstsGitPush": "OnGitPush",
    "OnVstsTfvcCheckIn": "OnTfvcCheckIn",
    "OnVstsWorkItemAssigned": "OnWorkItemAssignedV2",
    "OnVstsWorkItemClosed": "OnWorkItemClosedV2",
    "OnVstsWorkItemCreated": "OnWorkItemCreatedV2",
    "OnVstsWorkItemUpdated": "OnWorkItemUpdatedV2",
}
READ_ONLY = {"provisioningState", "pollingEndpoints"}
PENDING = {"Accepted", "Creating", "Updating", "Running"}
FAILED = {"Failed", "Canceled", "Cancelled"}
# Required wire keys from the local Python SDK trigger metadata at ef2011621f4ad64838a8a18c5720aef840fdfe46.
REQUIRED_PARAMETERS = {
    operation: ("account", "project", "repository") if operation in {
        "OnGitPullClosed", "OnGitPullCreated", "OnGitPush"}
    else ("account", "project", "team", "wiql__System_AssignedTo") if operation == "OnWorkItemAssignedV2"
    else ("account", "project")
    for operation in OPERATIONS.values()
}


def cli(program: str, arguments: list[str], *, interactive: bool = False) -> object:
    """Run the CLI; browser authentication inherits the terminal, never a capture pipe."""
    executable = shutil.which(program + ".cmd") if os.name == "nt" else None
    executable = executable or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is not installed.")
    command = [executable]
    if Path(executable).suffix.lower() in {".cmd", ".bat"}:
        interpreter = Path(executable).parent.parent / "python.exe"
        if program != "az" or not interpreter.is_file():
            raise RuntimeError("Install a native CLI executable or the Azure CLI MSI; batch wrappers are not supported.")
        # Bypass az.cmd's cmd.exe expansion of &, %, quotes, and other argument data.
        command = [str(interpreter), "-IBm", "azure.cli"]
    result = subprocess.run(
        [*command, *arguments], capture_output=not interactive,
        text=True, encoding="utf-8", timeout=660 if interactive else 120,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"'{program}' failed. Resolve the CLI error and rerun the hook.")
    if interactive or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise ValueError(f"'{program}' returned invalid JSON.") from None


def dns_hostname(hostname: object) -> str:
    """Accept a full DNS hostname, not credentials, an address, or malformed labels."""
    if (not isinstance(hostname, str) or len(hostname) > 253 or "." not in hostname
            or any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                   for label in hostname.split("."))):
        raise ValueError("Invalid service DNS hostname.")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return hostname.lower()
    raise ValueError("Service hostname must not be an IP address.")


def https_uri(uri: object):
    """Reject unsafe HTTPS origins and control characters before using a service URI."""
    if not isinstance(uri, str) or any(ord(character) <= 32 for character in uri) or "\\" in uri:
        raise ValueError("Invalid service HTTPS URI.")
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid service HTTPS URI.") from None
    if (parsed.scheme.lower() != "https" or parsed.username is not None or parsed.password is not None
            or port not in (None, 443) or parsed.fragment):
        raise ValueError("Unsafe service HTTPS URI origin.")
    dns_hostname(parsed.hostname)
    return parsed


def protect_path(path: Path) -> None:
    """Restrict a secret file or directory to the current Windows token's SID."""
    if os.name != "nt":
        os.chmod(path, 0o700 if path.is_dir() else 0o600)
        return
    import ctypes
    from ctypes import wintypes

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
            raise RuntimeError("Cannot obtain the current identity for private settings files.")
        size = wintypes.DWORD()
        security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not size.value:
            raise RuntimeError("Cannot read the current identity for private settings files.")
        user = ctypes.create_string_buffer(size.value)
        if (not security.GetTokenInformation(token, 1, user, size, ctypes.byref(size))
                or not security.ConvertSidToStringSidW(ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p)).contents.value, ctypes.byref(sid_text))):
            raise RuntimeError("Cannot read the current user SID for private settings files.")
        inheritance = "OICI" if path.is_dir() else ""
        if (not security.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                f"D:P(A;{inheritance};FA;;;{sid_text.value})", 1, ctypes.byref(descriptor), None)
                or not security.SetFileSecurityW(str(path), 0x80000004, descriptor)):
            raise RuntimeError("Cannot restrict private settings files to the current user.")
    finally:
        if descriptor.value:
            kernel.LocalFree(descriptor)
        if sid_text:
            kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        if token.value:
            kernel.CloseHandle(token)


@contextmanager
def private_json(value: object):
    """Keep callback keys and settings in an owned temporary directory, then remove it."""
    with tempfile.TemporaryDirectory(prefix="vsts-setup-") as directory:
        protect_path(Path(directory))
        path = Path(directory) / "request.json"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream)
        yield "@" + str(path)


def context(outputs: dict, mode: str) -> dict:
    """Validate deployment identity before constructing any Azure request."""
    required = (
        "resourceGroupName", "functionAppName", "FUNCTION_APP_HOSTNAME",
        "connectorNamespaceName", "connectorNamespaceResourceId",
        "connectorNamespaceConnectionName", "CONNECTOR_NAMESPACE_LOCATION", "deliveryMode",
    )
    if any(not isinstance(outputs.get(key), str) or not outputs[key] for key in required):
        raise ValueError("Missing deployment outputs. Provision this mode's project first.")
    match = re.fullmatch(
        r"/subscriptions/([\w-]+)/resourceGroups/([\w.-]+)/providers/Microsoft.Web/connectorGateways/([\w-]+)",
        outputs["connectorNamespaceResourceId"], re.IGNORECASE,
    )
    if (not match or match[2].lower() != outputs["resourceGroupName"].lower()
            or match[3].lower() != outputs["connectorNamespaceName"].lower()
            or outputs["deliveryMode"] != mode
            or not re.fullmatch(r"[a-z0-9-]+-entra", outputs["connectorNamespaceConnectionName"])
            or not re.fullmatch(r"[\w-]+", outputs["functionAppName"])):
        raise ValueError("Deployment outputs do not match this mode or its Entra connection.")
    dns_hostname(outputs["FUNCTION_APP_HOSTNAME"])
    if outputs.get("AZURE_SUBSCRIPTION_ID", match[1]).lower() != match[1].lower():
        raise ValueError("Deployment subscription outputs disagree.")
    root = "https://management.azure.com" + outputs["connectorNamespaceResourceId"]
    return {"subscription": match[1], "root": root, "collection": root + "/triggerConfigs"}


def rest(run, ctx: dict, method: str, url: str, body: object = None) -> dict:
    """Pin every ARM request to the provisioned subscription."""
    arguments = ["rest", "--method", method, "--url",
                 url if "?" in url else url + "?api-version=" + API_VERSION,
                 "--subscription", ctx["subscription"], "-o", "json"]
    if body is None:
        result = run("az", arguments)
    else:
        with private_json(body) as path:
            result = run("az", arguments + ["--body", path])
    if not isinstance(result, dict):
        raise ValueError("Invalid ARM response.")
    return result


def check_connection(connection: dict) -> bool:
    """Reject legacy OAuth on every connection read, including after authentication."""
    properties = connection.get("properties", {})
    if not isinstance(properties, dict) or not isinstance(properties.get("parameterValueSet"), dict):
        raise ValueError("Connection returned no authentication metadata. Check the deployment and rerun.")
    if properties["parameterValueSet"].get("name") != "EntraOAuth":
        raise ValueError("An EntraOAuth connection is required. Reprovision with the distinct -entra name; legacy OAuth cannot migrate in place.")
    return str(properties.get("overallStatus", "")).lower() == "connected"


def authorize(run, ctx: dict, outputs: dict, *, wait=time.sleep) -> dict:
    """Preserve working consent or complete interactive Entra authentication once."""
    url = ctx["root"] + "/connections/" + quote(outputs["connectorNamespaceConnectionName"], safe="")
    connection = rest(run, ctx, "GET", url)
    for attempt in range(30):
        connected = check_connection(connection)
        state = str(connection.get("properties", {}).get("provisioningState", "")).lower()
        if state in {value.lower() for value in FAILED}:
            raise ValueError("Connection provisioning failed. Resolve the deployment before consenting.")
        if state not in {value.lower() for value in PENDING}:
            break
        if attempt == 29:
            raise TimeoutError("Connection provisioning did not become ready in time.")
        wait(2)
        connection = rest(run, ctx, "GET", url)
    if not connected:
        print("Complete Azure DevOps Entra consent in your browser; keep this terminal open.")
        run("az", ["connector-namespace", "connection", "authenticate",
                   "-g", outputs["resourceGroupName"], "--namespace", outputs["connectorNamespaceName"],
                   "--connection-name", outputs["connectorNamespaceConnectionName"],
                   "--subscription", ctx["subscription"], "--timeout", "300", "--no-access-policy"],
            interactive=True)
        connection = rest(run, ctx, "GET", url)
        if not check_connection(connection):
            raise ValueError("Connection is not Connected after authentication. Resolve consent and rerun postdeploy.")
    return connection


def resolve(swagger: dict, schema: dict, visited: frozenset = frozenset()) -> dict:
    """Resolve local JSON Pointer references, rejecting cycles and external references."""
    if not isinstance(schema, dict):
        raise ValueError("Invalid connector parameter schema.")
    reference = schema.get("$ref")
    if not reference:
        return schema
    if not isinstance(reference, str) or not reference.startswith("#/") or reference in visited:
        raise ValueError("Unsupported or cyclic connector schema reference.")
    target = swagger
    try:
        for part in reference[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
    except (KeyError, TypeError):
        raise ValueError("Missing connector schema reference.") from None
    return {**resolve(swagger, target, visited | {reference}),
            **{key: value for key, value in schema.items() if key != "$ref"}}


def parameters_for(swagger: dict, operation: str) -> list[dict]:
    """Use the actual exported operation parameters, not Python-normalized names."""
    matches = []
    for methods in swagger.get("paths", {}).values():
        if not isinstance(methods, dict):
            raise ValueError("Invalid connector operation metadata.")
        for method, definition in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(definition, dict):
                raise ValueError("Invalid connector operation definition.")
            if definition.get("operationId") == operation:
                merged = {}
                if not isinstance(methods.get("parameters", []), list) or not isinstance(definition.get("parameters", []), list):
                    raise ValueError("Invalid connector parameter definitions.")
                for parameter in methods.get("parameters", []) + definition.get("parameters", []):
                    parameter = resolve(swagger, parameter)
                    merged[(parameter.get("in"), parameter.get("name"))] = parameter
                matches.append([parameter for parameter in merged.values()
                                if parameter.get("name") != "connectionId"
                                and parameter.get("x-ms-visibility") != "internal"
                                and not parameter.get("readOnly")])
    if len(matches) != 1:
        raise ValueError(f"Connector must expose exactly one '{operation}' operation in this region.")
    return matches[0]


def validate_inputs(selected: object, swagger: dict) -> dict:
    """Validate the selected subset and exact string wire parameters before writes."""
    validate_selection(selected)
    result = {}
    for trigger in selected:
        if not isinstance(trigger, dict) or set(trigger) != {"functionName", "operationName", "parameters"}:
            raise ValueError("Each trigger needs only functionName, operationName, and parameters.")
        function = trigger["functionName"]
        if not isinstance(function, str) or function not in OPERATIONS or function in result:
            raise ValueError("Unknown or duplicate selected function.")
        if trigger["operationName"] != OPERATIONS[function] or not isinstance(trigger["parameters"], list):
            raise ValueError("Selected operation does not match the nine-event inventory.")
        schemas = parameters_for(swagger, OPERATIONS[function])
        if any(schema.get("in") not in {"path", "query"} or schema.get("type") != "string" for schema in schemas):
            raise ValueError("Unsupported input schema; no wire parameters will be guessed.")
        for schema in schemas:
            if (not isinstance(schema.get("name"), str)
                    or any(type(schema[field]) is not int or schema[field] < 0 for field in ("minLength", "maxLength") if field in schema)
                    or "enum" in schema and not isinstance(schema["enum"], list)):
                raise ValueError("Invalid connector string parameter constraints.")
            if "pattern" in schema:
                try:
                    re.compile(schema["pattern"])
                except (TypeError, re.error):
                    raise ValueError("Unsupported connector parameter pattern; no sources were changed.") from None
        expected = {schema["name"]: schema for schema in schemas}
        values = {}
        for item in trigger["parameters"]:
            if not isinstance(item, dict) or set(item) != {"name", "value"}:
                raise ValueError("Each parameter needs only name and value.")
            name, value = item["name"], item["value"]
            if not isinstance(name, str) or name not in expected or name in values or not isinstance(value, str):
                raise ValueError("Unknown, duplicate, or non-string wire parameter.")
            schema = expected[name]
            if (schema.get("required") and not value.strip()
                    or len(value) < schema.get("minLength", 0)
                    or len(value) > schema.get("maxLength", sys.maxsize)
                    or "enum" in schema and value not in schema["enum"]
                    or "pattern" in schema and not re.search(schema["pattern"], value)):
                raise ValueError("Wire parameter does not satisfy the exported connector schema.")
            values[name] = value
        if any(schema.get("required") and schema["name"] not in values for schema in schemas):
            raise ValueError(f"{function}: missing required wire parameter; review the mode README and connector reference.")
        result[function] = trigger["parameters"]
    return result


def validate_selection(selected: object) -> None:
    """Reject malformed and incomplete reviewed inputs locally, before any CLI call."""
    if not isinstance(selected, list) or not selected:
        raise ValueError("Select at least one trigger in trigger-inputs.json; see the mode README.")
    functions = set()
    for trigger in selected:
        if (not isinstance(trigger, dict) or set(trigger) != {"functionName", "operationName", "parameters"}
                or not isinstance(trigger["functionName"], str) or trigger["functionName"] not in OPERATIONS
                or trigger["functionName"] in functions
                or trigger["operationName"] != OPERATIONS[trigger["functionName"]]
                or not isinstance(trigger["parameters"], list)):
            raise ValueError("Use distinct functions and their exact operation names from the mode README.")
        functions.add(trigger["functionName"])
        parameters = {}
        for parameter in trigger["parameters"]:
            if (not isinstance(parameter, dict) or set(parameter) != {"name", "value"}
                    or not isinstance(parameter["name"], str) or not parameter["name"]
                    or parameter["name"] in parameters or not isinstance(parameter["value"], str)):
                raise ValueError("Each parameter needs a distinct name and a string value; see trigger-inputs.example.json.")
            parameters[parameter["name"]] = parameter["value"]
        missing = [name for name in REQUIRED_PARAMETERS[trigger["operationName"]]
                   if not parameters.get(name, "").strip()]
        if missing:
            raise ValueError(f"{trigger['functionName']}: supply required wire keys {', '.join(missing)}; see the mode README.")


def list_triggers(run, ctx: dict) -> list[dict]:
    """Follow bounded, same-collection HTTPS pagination, including empty pages."""
    target = urlsplit(ctx["collection"])
    url = ctx["collection"] + "?api-version=" + API_VERSION
    resources, visited = [], set()
    while url:
        if not isinstance(url, str):
            raise ValueError("Invalid trigger continuation URL.")
        parsed = https_uri(url)
        identity = (parsed.hostname.lower(), parsed.path.lower(), parsed.query)
        if (parsed.hostname.lower() != target.hostname.lower()
            or parsed.path.lower() != target.path.lower()
            or identity in visited or len(visited) >= 100):
            raise ValueError("Unsafe, repeated, or excessive trigger continuation URL.")
        visited.add(identity)
        response = rest(run, ctx, "GET", url)
        if not isinstance(response.get("value"), list):
            raise ValueError("Invalid trigger inventory response.")
        if any(not isinstance(resource, dict) or not isinstance(resource.get("name"), str)
               or not isinstance(resource.get("id"), str) for resource in response["value"]):
            raise ValueError("Invalid trigger resource identity in inventory; no sources were changed.")
        resources.extend(response["value"])
        url = response.get("nextLink")
    return resources


def metadata(outputs: dict, ctx: dict, function: str) -> dict:
    """Describe the owning app for both delivery modes."""
    return {"destinationType": "functionApp", "functionAppSubscriptionId": ctx["subscription"],
            "functionAppResourceGroup": outputs["resourceGroupName"],
            "functionAppName": outputs["functionAppName"], "functionName": function}


def owned(resource: dict, ctx: dict, outputs: dict, function: str, name: str, mode: str) -> None:
    """Verify full resource identity, operation, connection, delivery, and app ownership."""
    properties = resource.get("properties", {})
    delivery = properties.get("deliveryMode", "Webhook")
    expected_mode = "Poll" if mode == "polling" else "Webhook"
    if (str(resource.get("id", "")).lower() != (urlsplit(ctx["collection"]).path + "/" + name).lower()
            or str(resource.get("name", "")).lower() != name.lower()
            or properties.get("operationName") != OPERATIONS[function]
            or properties.get("connectionDetails") != {
                "connectorName": CONNECTOR, "connectionName": outputs["connectorNamespaceConnectionName"]}
            or delivery != expected_mode
            or any(properties.get("metadata", {}).get(key) != value
                   for key, value in metadata(outputs, ctx, function).items())):
        raise ValueError(f"Refusing to overwrite unowned or other-mode source '{name}'.")


def poll_endpoint(uri: object, name: str, gateway_host: str | None = None) -> str:
    """Derive the runtime prefix only from a validated service-issued receive URI."""
    if not isinstance(uri, str):
        raise ValueError("Polling source returned no receive URI.")
    parsed = https_uri(uri)
    if gateway_host and parsed.hostname.lower() != gateway_host.lower():
        raise ValueError("Inconsistent polling receive URI origin.")
    match = re.fullmatch(r"(/api(?:/connectorGateways/[^/]+)?)/triggerconfigs/([^/]+)/receive", parsed.path, re.IGNORECASE)
    if (not match or unquote(match[2]).lower() != name.lower()
            or any(part in {".", ".."} for part in unquote(match[1]).split("/"))
            or "%" in match[1]):
        raise ValueError("Polling receive URI does not match the expected source path.")
    prefix = "" if match[1].lower() == "/api" else match[1]
    return "https://" + parsed.hostname.lower() + prefix


def wait_ready(run, ctx: dict, url: str, resource: dict, *, require_receive: bool, wait=time.sleep) -> dict:
    """Bound provisioning and polling endpoint reads; never enable listeners early."""
    for attempt in range(30):
        properties = resource.get("properties", {})
        state = properties.get("provisioningState")
        state = str(state or "").lower()
        if state in {value.lower() for value in FAILED}:
            raise ValueError("Source registration failed. Resolve permissions and rerun postdeploy.")
        if (properties and state in {"", "succeeded"}
                and (not require_receive or properties.get("pollingEndpoints", {}).get("receiveUri"))):
            return resource
        if attempt < 29:
            wait(2)
            resource = rest(run, ctx, "GET", url)
    raise TimeoutError("Source registration or receive URI did not become ready in time.")


def write_local(project: Path, values: dict, *, force: bool) -> None:
    """Atomically create local settings; preserve existing content unless forced."""
    destination = project / "local.settings.json"
    if destination.exists() and not force:
        print("Existing local.settings.json preserved; review settings before local testing.")
        return
    document = json.loads((destination if destination.exists() else project / "local.settings.example.json").read_text(encoding="utf-8"))
    if not isinstance(document.get("Values"), dict) or document.get("IsEncrypted") is not False:
        raise ValueError("Local settings must be an unencrypted Values object.")
    document["Values"].update(values)
    document["Values"].pop("ConnectorNamespace__credential", None)
    document["Values"].pop("VstsConnection__credential", None)
    descriptor, temporary = tempfile.mkstemp(prefix=".vsts-settings-", dir=project)
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


def setup(outputs: dict, selected: object, mode: str, project: Path, *, run=cli,
          wait=time.sleep, force_local: bool = False) -> None:
    """Preflight the full plan, then reconcile only owned sources and enable listeners last."""
    ctx = context(outputs, mode)
    validate_selection(selected)
    connection = authorize(run, ctx, outputs, wait=wait)
    runtime = connection.get("properties", {}).get("connectionRuntimeUrl")
    if mode == "webhook":
        https_uri(runtime)
    exported = rest(run, ctx, "GET", "https://management.azure.com/subscriptions/" + ctx["subscription"]
                    + "/providers/Microsoft.Web/locations/" + quote(outputs["CONNECTOR_NAMESPACE_LOCATION"], safe="")
                    + "/managedApis/" + CONNECTOR + "?api-version=2016-06-01&export=true")
    swagger = exported.get("properties", {}).get("apiDefinitions", {}).get("value", exported)
    if isinstance(swagger, str):
        swagger = json.loads(swagger)
    if not isinstance(swagger, dict) or not isinstance(swagger.get("paths"), dict):
        raise ValueError("Connector exported no operation metadata.")
    selections = validate_inputs(selected, swagger)
    app = rest(run, ctx, "GET", "https://management.azure.com/subscriptions/" + ctx["subscription"]
               + "/resourceGroups/" + outputs["resourceGroupName"] + "/providers/Microsoft.Web/sites/" + outputs["functionAppName"])
    if dns_hostname(app.get("properties", {}).get("defaultHostName")) != dns_hostname(outputs["FUNCTION_APP_HOSTNAME"]):
        raise ValueError("Actual Function App hostname disagrees with deployment output.")
    key = None
    if mode == "webhook":
        for attempt in range(30):
            try:
                keys = run("az", ["functionapp", "keys", "list", "-g", outputs["resourceGroupName"],
                                  "-n", outputs["functionAppName"], "--subscription", ctx["subscription"], "-o", "json"])
                key = keys.get("systemKeys", {}).get("connector_extension") if isinstance(keys, dict) else None
            except RuntimeError:
                key = None
            if isinstance(key, str) and key:
                break
            if attempt < 29:
                wait(2)
        if not isinstance(key, str) or not key:
            raise ValueError("No connector_extension system key. Check host startup and rerun postdeploy.")
    inventory = list_triggers(run, ctx)
    plan = []
    existing_endpoint = None
    for function in OPERATIONS:
        name = outputs["connectorNamespaceConnectionName"] + "-" + function.lower()
        expected_id = urlsplit(ctx["collection"]).path + "/" + name
        matches = [resource for resource in inventory if isinstance(resource, dict)
                   and (str(resource.get("name", "")).lower() == name.lower()
                        or str(resource.get("id", "")).lower() == expected_id.lower())]
        if len(matches) > 1:
            raise ValueError("Duplicate source inventory entries.")
        url = ctx["collection"] + "/" + name
        resource = rest(run, ctx, "GET", url) if matches else None
        if resource:
            resource = wait_ready(run, ctx, url, resource, require_receive=False, wait=wait)
            owned(resource, ctx, outputs, function, name, mode)
            if mode == "polling" and resource["properties"].get("pollingEndpoints", {}).get("receiveUri"):
                received = poll_endpoint(resource["properties"]["pollingEndpoints"]["receiveUri"], name)
                if existing_endpoint and received != existing_endpoint:
                    raise ValueError("Existing sources returned inconsistent polling endpoints.")
                existing_endpoint = received
        plan.append((function, name, url, resource))
    # Complete every ownership check before the first settings or trigger write.
    disabled = {"AzureWebJobs." + function + ".Disabled": "true" for function in OPERATIONS}
    settings_arguments = ["functionapp", "config", "appsettings", "set", "-g", outputs["resourceGroupName"],
                          "-n", outputs["functionAppName"], "--subscription", ctx["subscription"], "-o", "none"]
    with private_json(disabled) as path:
        run("az", settings_arguments + ["--settings", path])
    cloud, local, endpoint = {}, {}, None
    for function, name, url, resource in plan:
        active = function in selections
        cloud["AzureWebJobs." + function + ".Disabled"] = str(not active).lower()
        local["AzureWebJobs." + function + ".Disabled"] = str(not active).lower()
        if mode == "polling":
            cloud[function + "TriggerConfigName"] = name
            local[function + "TriggerConfigName"] = name
        if not active:
            if resource and resource["properties"].get("state") != "Disabled":
                properties = {field: copy.deepcopy(value) for field, value in resource["properties"].items() if field not in READ_ONLY}
                properties["state"] = "Disabled"
                disabled_resource = rest(run, ctx, "PUT", url, {"properties": properties})
                disabled_resource = wait_ready(run, ctx, url, disabled_resource, require_receive=False, wait=wait)
                owned(disabled_resource, ctx, outputs, function, name, mode)
                if disabled_resource["properties"].get("state") != "Disabled":
                    raise ValueError("Deselected source was not disabled.")
            continue
        properties = {field: copy.deepcopy(value) for field, value in (resource or {}).get("properties", {}).items() if field not in READ_ONLY}
        properties.update(connectionDetails={"connectorName": CONNECTOR, "connectionName": outputs["connectorNamespaceConnectionName"]},
                          operationName=OPERATIONS[function], parameters=selections[function], state="Enabled")
        properties.setdefault("metadata", {}).update(metadata(outputs, ctx, function))
        properties.setdefault("type", "NotSpecified")
        properties.setdefault("description", "Azure DevOps " + function)
        if mode == "polling":
            properties["deliveryMode"] = "Poll"
            properties.pop("notificationDetails", None)
        else:
            notification = properties.setdefault("notificationDetails", {})
            notification.update({
                "callbackUrl": "https://" + outputs["FUNCTION_APP_HOSTNAME"] + "/runtime/webhooks/connector?functionName=" + function,
                "httpMethod": "Post",
            })
            notification.setdefault("authentication", {}).update(type="QueryString", name="code", value=key)
        previous = {field: value for field, value in (resource or {}).get("properties", {}).items() if field not in READ_ONLY}
        ordered = lambda items: sorted(items, key=lambda item: item["name"])
        unchanged = bool(resource) and {**previous, "parameters": ordered(previous.get("parameters", []))} == {**properties, "parameters": ordered(properties["parameters"])}
        created = resource if unchanged else rest(run, ctx, "PUT", url, {"properties": properties})
        created = wait_ready(run, ctx, url, created, require_receive=mode == "polling", wait=wait)
        owned(created, ctx, outputs, function, name, mode)
        if created["properties"].get("state") != "Enabled":
            raise ValueError("Selected source was not enabled.")
        if mode == "polling":
            received = poll_endpoint(created["properties"]["pollingEndpoints"]["receiveUri"], name,
                                     urlsplit(endpoint).hostname if endpoint else None)
            if endpoint and received != endpoint:
                raise ValueError("Selected sources returned inconsistent polling endpoints.")
            endpoint = received
        print(f"Configured {function} ({mode}).")
    if mode == "polling":
        cloud.update(ConnectorNamespace__credential="managedidentity", ConnectorNamespace__pollingEndpoint=endpoint)
        local["ConnectorNamespace__pollingEndpoint"] = endpoint
    else:
        cloud["VstsConnection"] = runtime
        local["VstsConnection"] = runtime
    with private_json(cloud) as path:
        run("az", settings_arguments + ["--settings", path])
    write_local(project, local, force=force_local)
    print("Old connections or callback subscriptions need manual review and source cleanup. No unowned sources were deleted.")


def main(argv: list[str] | None = None) -> None:
    """Require reviewed mode-local inputs; never offer an undocumented automatic picker."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("polling", "webhook"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--force-local-settings", action="store_true")
    parser.add_argument("--check-inputs", action="store_true")
    options = parser.parse_args(argv)
    project = options.project.resolve()
    path = options.inputs or project / "trigger-inputs.json"
    if not path.is_file():
        raise ValueError("Create this mode's trigger-inputs.json from the reviewed example before azd up. See the mode README; no sources were changed.")
    selected = json.loads(path.read_text(encoding="utf-8"))
    validate_selection(selected)
    if options.check_inputs:
        print("Reviewed input structure and required keys checked locally. Full wire schemas will be checked before registration.")
        return
    outputs = cli("azd", ["env", "get-values", "--output", "json"])
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd outputs.")
    setup(outputs, selected, options.mode, project, force_local=options.force_local_settings)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, TimeoutError, subprocess.SubprocessError) as error:
        if isinstance(error, (ValueError, RuntimeError)) and not isinstance(error, json.JSONDecodeError):
            print(str(error), file=sys.stderr)
        print("Azure DevOps setup failed. Check reviewed inputs, Entra consent, app identity, and source registration. A failed registration does not enable new listeners. No callback keys were printed.", file=sys.stderr)
        sys.exit(1)