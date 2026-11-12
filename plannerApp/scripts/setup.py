# Copyright (c) Microsoft Corporation.  All rights reserved.
# Licensed under the MIT License.

"""Configure Planner sources after deployment and consent, without logging secrets."""

from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

API_VERSION = "2026-05-01-preview"
OPERATIONS = {
    "OnPlannerCompleteTask": ("OnCompleteTask_V3", ("groupId", "id")),
    "OnPlannerNewTask": ("OnNewTask_V3", ("groupId", "id")),
    "OnPlannerTaskAssignedToMe": ("OnTaskAssignedToMe_V2", ()),
}
READ_ONLY = ("provisioningState", "pollingEndpoints", "statuses", "overallStatus",
             "createdTime", "changedTime")
PENDING = {"Accepted", "Creating", "Updating", "Running"}
FAILED = {"Failed", "Canceled", "Cancelled"}


def cli(program: str, *arguments: str, interactive: bool = False) -> Any:
    """Inherit the terminal for OAuth; capture JSON and redact other failures."""
    executable = (shutil.which(program + ".cmd") if os.name == "nt" else None)
    executable = executable or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is not installed.")
    try:
        result = subprocess.run(
            [executable, *arguments], capture_output=not interactive, text=True,
            encoding="utf-8", timeout=360 if interactive else 120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError(f"'{program}' failed or timed out; output withheld.") from None
    if result.returncode:
        raise RuntimeError(f"'{program}' failed; command output withheld.")
    if interactive or not result.stdout or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise RuntimeError(f"'{program}' returned invalid JSON; output withheld.") from None


def protect_directory(directory: Path) -> None:
    """Restrict staging to the current user on Windows and POSIX."""
    if os.name != "nt":
        directory.chmod(0o700)
        return
    identity = subprocess.run(
        ["whoami.exe", "/user", "/fo", "csv", "/nh"],
        capture_output=True, text=True, check=True,
    )
    import csv

    sid = next(csv.reader([identity.stdout.strip()]))[1]
    result = subprocess.run(
        ["icacls.exe", str(directory), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F",
         "/remove:g", "*S-1-3-4", "*S-1-5-18", "*S-1-5-32-544"],
        capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError("Could not restrict private staging permissions.")


@contextmanager
def private_json(value: Any) -> Iterator[str]:
    """Create JSON only after restricting its directory; always remove it."""
    directory = Path(tempfile.mkdtemp(prefix="planner-setup-"))
    try:
        protect_directory(directory)
        path = directory / "request.json"
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        yield "@" + str(path)
    finally:
        shutil.rmtree(directory)


def regular_file(path: Path) -> bool:
    """Reject links, junctions and directories before writing local settings."""
    if (path.is_symlink() or getattr(path, "is_junction", lambda: False)() or
            (path.exists() and not path.is_file())):
        raise ValueError("Settings must be a regular file.")
    return path.exists()


def write_local_settings(path: Path, values: dict[str, str], *, force: bool = False) -> bool:
    """Atomically write private settings, preserving existing bytes by default."""
    if regular_file(path) and not force:
        print("Existing local settings preserved byte-for-byte.")
        return False
    with private_json({"IsEncrypted": False, "Values": values}) as source:
        # Stage on the destination volume so rename and exclusive linking are atomic.
        directory = Path(tempfile.mkdtemp(prefix=".planner-settings-", dir=path.parent))
        try:
            protect_directory(directory)
            staging = directory / "settings.json"
            shutil.copyfile(source[1:], staging)
            staging.chmod(0o600)
            with staging.open("r+b") as stream:
                os.fsync(stream.fileno())
            regular_file(path)
            if force:
                os.replace(staging, path)
            else:
                os.link(staging, path)
        finally:
            shutil.rmtree(directory)
    print("Created private, ignored local settings.")
    return True


def validate_selection(items: Any) -> list[dict[str, Any]]:
    """Require distinct reviewed operations and exact, non-placeholder wire keys."""
    if not isinstance(items, list) or not items:
        raise ValueError("Select at least one Planner trigger before setup.")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"functionName", "operationName", "parameters"}:
            raise ValueError("Invalid trigger input fields.")
        function = item["functionName"]
        if not isinstance(function, str) or function not in OPERATIONS or function in seen:
            raise ValueError("Select distinct supported Planner functions.")
        seen.add(function)
        operation, required = OPERATIONS[function]
        parameters = item["parameters"]
        if item["operationName"] != operation or not isinstance(parameters, list):
            raise ValueError("Function and operation do not match the reviewed contract.")
        names = []
        for parameter in parameters:
            if not isinstance(parameter, dict) or set(parameter) != {"name", "value"}:
                raise ValueError("Invalid parameter fields.")
            if not isinstance(parameter["name"], str):
                raise ValueError("Parameter names must be strings.")
            value = parameter["value"]
            if (not isinstance(value, str) or not value.strip() or value != value.strip() or
                    any(character in value for character in "<>\r\n") or
                    value.casefold() in {"todo", "changeme", "placeholder", "group-id", "plan-id"}):
                raise ValueError("Supply actual non-empty Planner identifiers, not placeholders.")
            names.append(parameter["name"])
        if len(names) != len(set(names)) or set(names) != set(required):
            raise ValueError("Planner parameters must match the reviewed required wire keys.")
    return copy.deepcopy(items)


def select_inputs(project: Path, inputs: Path | None, prompt: Callable[[str], str] = input) -> list[dict[str, Any]]:
    """Read user-authored inputs, or prompt for real IDs without claiming a picker."""
    contract = json.loads((project / "infra/triggers.json").read_text(encoding="utf-8"))
    expected = [{"functionName": name, "operationName": operation,
                 "requiredParameters": list(required)}
                for name, (operation, required) in OPERATIONS.items()]
    if contract != expected:
        raise ValueError("The local reviewed Planner contract has changed.")
    configured = inputs or project / "trigger-inputs.json"
    if configured.exists():
        return validate_selection(json.loads(configured.read_text(encoding="utf-8")))
    if inputs:
        raise ValueError("The requested trigger input file does not exist.")
    environment = os.environ.get("PLANNER_TRIGGER_INPUTS")
    if environment:
        return validate_selection(json.loads(environment))
    selected = []
    for function, (operation, required) in OPERATIONS.items():
        answer = prompt(f"Configure {function}? [y/N]: ").strip().casefold()
        if answer not in ("", "n", "no", "y", "yes"):
            raise ValueError("Answer yes or no; no sources have changed.")
        if answer not in ("y", "yes"):
            continue
        parameters = []
        for name in required:
            setting = "PLANNER_GROUP_ID" if name == "groupId" else "PLANNER_PLAN_ID"
            value = os.environ.get(setting) or prompt(
                f"Actual {'group ID' if name == 'groupId' else 'plan ID (not task ID)'}: "
            ).strip()
            parameters.append({"name": name, "value": value})
        selected.append({"functionName": function, "operationName": operation, "parameters": parameters})
    return validate_selection(selected)


def polling_endpoint(receive_uri: Any, name: str) -> str:
    """Extract the service gateway from a verified HTTPS trigger receive URI."""
    if not isinstance(receive_uri, str):
        raise ValueError("The service did not return a polling receive URI.")
    parsed = urlsplit(receive_uri)
    marker = "/triggerconfigs/"
    path = unquote(parsed.path)
    index = path.casefold().find(marker)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or
            parsed.fragment or parsed.port not in (None, 443) or index <= 0 or
            path[index + len(marker):].casefold() != (name + "/receive").casefold()):
        raise ValueError("Invalid service polling receive URI.")
    if parsed.hostname.casefold() in {"localhost", "example.com", "example.invalid"}:
        raise ValueError("A real service polling hostname is required.")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("A service DNS hostname is required.")
    prefix = parsed.path[:parsed.path.casefold().index(marker)]
    if any(segment in {".", ".."} for segment in unquote(prefix).split("/")):
        raise ValueError("The service polling gateway path is invalid.")
    if prefix.casefold().endswith("/api"):
        prefix = prefix[:-4]
    return f"https://{parsed.netloc}{prefix}"


class Setup:
    """Keep all Azure commands pinned to one explicit subscription."""

    def __init__(self, outputs: dict[str, str], mode: str,
                 run: Callable[..., Any] = cli, wait: Callable[[float], None] = time.sleep) -> None:
        self.outputs = outputs
        self.mode = mode
        self.run = run
        self.wait = wait
        for name in ("AZURE_SUBSCRIPTION_ID", "resourceGroupName", "functionAppName",
                     "functionAppDefaultHostname", "connectorNamespaceName", "connectorNamespaceConnectionName"):
            if not isinstance(outputs.get(name), str) or not outputs[name].strip():
                raise ValueError(f"Missing azd output '{name}'. Provision this mode first.")
        if mode not in {"polling", "webhook"}:
            raise ValueError("Invalid delivery mode.")
        self.root = ("https://management.azure.com/subscriptions/" + quote(outputs["AZURE_SUBSCRIPTION_ID"], safe="") +
                     "/resourceGroups/" + quote(outputs["resourceGroupName"], safe="") +
                     "/providers/Microsoft.Web/connectorGateways/" + quote(outputs["connectorNamespaceName"], safe=""))
        self.collection = self.root + "/triggerConfigs"

    def az(self, *arguments: str, interactive: bool = False) -> Any:
        """Never let a different active CLI subscription select resources."""
        return self.run("az", *arguments, "--subscription", self.outputs["AZURE_SUBSCRIPTION_ID"],
                        interactive=interactive)

    def rest(self, method: str, url: str, properties: dict[str, Any] | None = None) -> Any:
        """Keep request secrets in a private file, not command arguments."""
        if properties is None:
            return self.az("rest", "--method", method, "--url", url, "-o", "json")
        with private_json({"properties": properties}) as body:
            return self.az("rest", "--method", method, "--url", url, "--body", body, "-o", "json")

    def authorize(self) -> None:
        """Require Connected before any trigger or settings writes."""
        arguments = ("-g", self.outputs["resourceGroupName"], "--namespace", self.outputs["connectorNamespaceName"],
                     "--connection-name", self.outputs["connectorNamespaceConnectionName"])

        def connected() -> bool:
            response = self.az("connector-namespace", "connection", "show", *arguments, "-o", "json")
            return isinstance(response, dict) and response.get("properties", {}).get("overallStatus") == "Connected"

        if connected():
            print("Planner connection is already Connected; consent preserved.")
            return
        print("Complete Planner OAuth in the browser and answer the CLI prompts in this terminal.")
        self.az("connector-namespace", "connection", "authenticate", *arguments,
                "--timeout", "300", "--no-access-policy", interactive=True)
        if not connected():
            raise ValueError("Planner OAuth did not reach Connected; no sources or settings changed.")

    def list_triggers(self) -> list[dict[str, Any]]:
        """Follow bounded same-collection continuations, including empty pages."""
        target = urlsplit(self.collection)
        visited: set[str] = set()
        url: Any = self.collection + "?api-version=" + API_VERSION
        resources = []
        while url:
            if not isinstance(url, str):
                raise ValueError("Invalid continuation URL.")
            parsed = urlsplit(url)
            if (parsed.scheme != target.scheme or parsed.netloc != target.netloc or parsed.fragment or
                    parsed.path.rstrip("/").casefold() != target.path.casefold() or url in visited or
                    len(visited) >= 100):
                raise ValueError("Invalid, repeated or excessive trigger continuation URL.")
            visited.add(url)
            page = self.rest("get", url)
            if not isinstance(page, dict) or not isinstance(page.get("value"), list):
                raise ValueError("Invalid trigger collection response.")
            if any(not isinstance(item, dict) for item in page["value"]):
                raise ValueError("Invalid trigger collection item.")
            resources.extend(page["value"])
            url = page.get("nextLink")
        return resources

    def name(self, function: str) -> str:
        """Use a connection-specific prefix and separate delivery-mode names."""
        return self.outputs["connectorNamespaceConnectionName"] + "-" + self.mode + "-" + function.lower()

    def metadata(self, function: str) -> dict[str, str]:
        """Identify the app, mode and function that own each subscription."""
        return {"sample": "planner-python", "deliveryMode": self.mode, "destinationType": "functionApp",
                "functionAppSubscriptionId": self.outputs["AZURE_SUBSCRIPTION_ID"],
                "functionAppResourceGroup": self.outputs["resourceGroupName"],
                "functionAppName": self.outputs["functionAppName"], "functionName": function}

    def owned(self, resource: Any, function: str) -> dict[str, Any]:
        """Reject foreign metadata, operations, connections, IDs and delivery modes."""
        name = self.name(function)
        properties = resource.get("properties") if isinstance(resource, dict) else None
        expected_id = urlsplit(self.collection).path + "/" + name
        modes = {"Poll"} if self.mode == "polling" else {None, "", "Webhook", "Push", "NotSpecified"}
        if (not isinstance(properties, dict) or resource.get("id", "").casefold() != expected_id.casefold() or
                resource.get("name", "").casefold() != name.casefold() or
                properties.get("operationName") != OPERATIONS[function][0] or
                properties.get("connectionDetails", {}).get("connectionName") != self.outputs["connectorNamespaceConnectionName"] or
                properties.get("connectionDetails", {}).get("connectorName") != "planner" or
                properties.get("deliveryMode") not in modes or
                any(properties.get("metadata", {}).get(key) != value for key, value in self.metadata(function).items())):
            raise ValueError("Refusing to change a trigger whose ownership does not match this app and mode.")
        return properties

    def settings(self, values: dict[str, str]) -> None:
        """Apply private settings and confirm every value without printing them."""
        arguments = ("-g", self.outputs["resourceGroupName"], "-n", self.outputs["functionAppName"])
        with private_json(values) as path:
            self.az("functionapp", "config", "appsettings", "set", *arguments, "--settings", path, "-o", "none")
        response = self.az("functionapp", "config", "appsettings", "list", *arguments, "-o", "json")
        if not isinstance(response, list):
            raise ValueError("Could not verify app settings.")
        actual = {item["name"]: item["value"] for item in response}
        if any(actual.get(name) != value for name, value in values.items()):
            raise ValueError("App settings verification failed; output withheld.")

    def configure(self, selection: list[dict[str, Any]]) -> dict[str, str]:
        """Preflight all ownership, register sources, then enable verified listeners."""
        selection = validate_selection(selection)
        selected = {item["functionName"]: item for item in selection}
        self.authorize()
        resources = self.list_triggers()
        existing: dict[str, dict[str, Any] | None] = {}
        urls = {function: self.collection + "/" + quote(self.name(function), safe="") +
                "?api-version=" + API_VERSION for function in OPERATIONS}
        # Check deselected sources too before the first PUT or settings update.
        for function in OPERATIONS:
            name = self.name(function)
            expected_id = urlsplit(self.collection).path + "/" + name
            matches = [item for item in resources if item.get("name", "").casefold() == name.casefold() or
                       item.get("id", "").casefold() == expected_id.casefold()]
            if len(matches) > 1:
                raise ValueError("Duplicate sample resource identities.")
            existing[function] = None
            if matches:
                self.owned(matches[0], function)
                current = self.rest("get", urls[function])
                self.owned(current, function)
                existing[function] = current
        callback: dict[str, Any] | None = None
        if self.mode == "webhook":
            hostname = self.outputs["functionAppDefaultHostname"]
            parsed = urlsplit("https://" + hostname)
            if parsed.netloc != hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.port:
                raise ValueError("Invalid actual Function App hostname.")
            key = None
            for attempt in range(30):
                try:
                    keys = self.az("functionapp", "keys", "list", "-g", self.outputs["resourceGroupName"],
                                   "-n", self.outputs["functionAppName"], "-o", "json")
                    key = keys.get("systemKeys", {}).get("connector_extension") if isinstance(keys, dict) else None
                except RuntimeError:
                    key = None
                if isinstance(key, str) and key:
                    break
                if attempt == 29:
                    raise ValueError("Deploy first: connector_extension system key is unavailable.")
                self.wait(2)
            callback = {"httpMethod": "Post", "authentication": {"type": "QueryString", "name": "code", "value": key}}
        values = {"PYTHON_ISOLATE_WORKER_DEPENDENCIES": "1", "ConnectorNamespace__credential": "managedidentity"}
        for function in OPERATIONS:
            values[f"AzureWebJobs.{function}.Disabled"] = "true"
            if self.mode == "polling":
                values[function + "TriggerConfigName"] = self.name(function)
        self.settings(values)
        endpoint = None
        for function in OPERATIONS:
            resource = existing[function]
            if not resource and function not in selected:
                continue
            properties = copy.deepcopy(resource["properties"]) if resource else {}
            for field in READ_ONLY:
                properties.pop(field, None)
            properties["state"] = "Enabled" if function in selected else "Disabled"
            if function in selected:
                properties.setdefault("type", "NotSpecified")
                properties.setdefault("description", "Planner Python " + function)
                properties.setdefault("connectionDetails", {}).update(
                    connectorName="planner", connectionName=self.outputs["connectorNamespaceConnectionName"])
                properties["operationName"] = OPERATIONS[function][0]
                properties["parameters"] = selected[function]["parameters"]
                properties.setdefault("metadata", {}).update(self.metadata(function))
                if self.mode == "polling":
                    properties["deliveryMode"] = "Poll"
                else:
                    properties.setdefault("notificationDetails", {}).update(
                        dict(callback or {}, callbackUrl="https://" + self.outputs["functionAppDefaultHostname"] +
                             "/runtime/webhooks/connector?functionName=" + function))
            unchanged = resource is not None and all(
                resource["properties"].get(key) == value for key, value in properties.items())
            unchanged = unchanged and resource["properties"].get("provisioningState") == "Succeeded"
            if not unchanged:
                self.rest("put", urls[function], properties)
            current = None
            for attempt in range(30):
                current = self.rest("get", urls[function])
                verified = self.owned(current, function)
                status = verified.get("provisioningState")
                if status in FAILED:
                    raise ValueError("Planner source registration failed; listeners remain disabled.")
                ready = status == "Succeeded" and all(verified.get(key) == value for key, value in properties.items())
                if ready and (self.mode != "polling" or function not in selected or
                              verified.get("pollingEndpoints", {}).get("receiveUri")):
                    break
                if attempt == 29:
                    raise TimeoutError("Planner source registration readiness timed out; listeners remain disabled.")
                self.wait(2)
            if self.mode == "polling" and function in selected:
                resolved = polling_endpoint(current["properties"]["pollingEndpoints"]["receiveUri"], self.name(function))
                if endpoint is not None and endpoint != resolved:
                    raise ValueError("Selected sources returned inconsistent polling gateways.")
                endpoint = resolved
        if self.mode == "polling":
            if not endpoint:
                raise ValueError("No verified polling gateway was returned.")
            values["ConnectorNamespace__pollingEndpoint"] = endpoint
        for function in OPERATIONS:
            values[f"AzureWebJobs.{function}.Disabled"] = str(function not in selected).lower()
        try:
            self.settings(values)
        except (ValueError, RuntimeError, OSError):
            try:
                self.settings({f"AzureWebJobs.{function}.Disabled": "true" for function in OPERATIONS})
            except (ValueError, RuntimeError, OSError):
                raise RuntimeError("Settings verification and listener rollback failed; manually disable this app.") from None
            raise
        print(f"Configured {len(selected)} Planner {self.mode} sources; listener settings verified.")
        return values


def main(argv: list[str] | None = None) -> None:
    """Run from either mode's postdeploy hook; import performs no Azure calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("polling", "webhook"), required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--force", action="store_true", help="Replace existing local settings.")
    options = parser.parse_args(argv)
    project = options.project.resolve()
    regular_file(project / "local.settings.json")
    selection = select_inputs(project, options.inputs)
    outputs = cli("azd", "env", "get-values", "--output", "json")
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd environment outputs.")
    values = Setup(outputs, options.mode).configure(selection)
    values.pop("ConnectorNamespace__credential", None)
    values.update(AzureWebJobsStorage="UseDevelopmentStorage=true", FUNCTIONS_WORKER_RUNTIME="python")
    write_local_settings(project / "local.settings.json", values, force=options.force)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, EOFError, subprocess.SubprocessError):
        print("Planner setup failed. Check consent, reviewed inputs, ownership and service readiness; details withheld.", file=sys.stderr)
        sys.exit(1)