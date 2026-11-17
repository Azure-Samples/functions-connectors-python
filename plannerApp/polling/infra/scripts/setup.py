# Copyright (c) Microsoft Corporation.  All rights reserved.
# Licensed under the MIT License.

"""Configure this standalone Planner app without logging settings or callback keys."""

from __future__ import annotations

import argparse
import base64
import copy
import csv
import ipaddress
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

API_VERSION = "2026-05-01-preview"
OPERATIONS = {
    "OnPlannerCompleteTask": ("OnCompleteTask_V3", ("groupId", "id")),
    "OnPlannerNewTask": ("OnNewTask_V3", ("groupId", "id")),
    "OnPlannerTaskAssignedToMe": ("OnTaskAssignedToMe_V2", ()),
}
READ_ONLY = ("provisioningState", "pollingEndpoints", "statuses", "overallStatus", "createdTime", "changedTime")


def cli(program, *arguments, interactive=False):
    """Leave OAuth prompts visible; capture all noninteractive output."""
    executable = (shutil.which(program + ".cmd") if os.name == "nt" else None) or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is not installed.")
    try:
        result = subprocess.run([executable, *arguments], capture_output=not interactive, text=True,
                                encoding="utf-8", timeout=360 if interactive else 120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError(f"'{program}' failed or timed out; output withheld.") from None
    if result.returncode:
        raise RuntimeError(f"'{program}' failed; output withheld.")
    if interactive or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise RuntimeError(f"'{program}' returned invalid JSON; output withheld.") from None


def protect_directory(directory):
    """Restrict staging to the current user before writing sensitive data."""
    if os.name != "nt":
        directory.chmod(0o700)
        return
    identity = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"],
                              capture_output=True, text=True, check=True)
    sid = next(csv.reader([identity.stdout.strip()]))[1]
    result = subprocess.run(
        ["icacls.exe", str(directory), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F",
         "/remove:g", "*S-1-3-4", "*S-1-5-18", "*S-1-5-32-544"], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("Could not restrict private staging permissions.")


@contextmanager
def private_json(value):
    """Use a private request file and remove it on every exit."""
    directory = Path(tempfile.mkdtemp(prefix="planner-setup-"))
    try:
        protect_directory(directory)
        descriptor = os.open(directory / "request.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        yield "@" + str(directory / "request.json")
    finally:
        shutil.rmtree(directory)


def regular_file(path):
    """Reject links, junctions and directories before writing settings."""
    if (path.is_symlink() or getattr(path, "is_junction", lambda: False)() or
            (path.exists() and not path.is_file())):
        raise ValueError("Settings must be a regular file.")
    return path.exists()


def write_local_settings(path, values, *, force=False):
    """Preserve existing bytes unless replacement is explicit; write atomically."""
    if regular_file(path) and not force:
        print("Existing local settings preserved byte-for-byte.")
        return False
    with private_json({"IsEncrypted": False, "Values": values}) as source:
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


def required(outputs, *names):
    """Fail before Azure writes if the selected environment lacks required outputs."""
    for name in names:
        if not isinstance(outputs.get(name), str) or not outputs[name].strip():
            raise ValueError(f"Missing azd output '{name}'. Provision the preceding layer first.")


def detect_app(outputs, run=None):
    """List apps, not settings; fail closed on inventory errors or ambiguity."""
    run = run or cli
    required(outputs, "AZURE_SUBSCRIPTION_ID", "AZURE_ENV_NAME")
    group = outputs.get("resourceGroupName") or "rg-" + outputs["AZURE_ENV_NAME"]
    apps = run("az", "functionapp", "list", "--subscription", outputs["AZURE_SUBSCRIPTION_ID"], "-o", "json")
    if not isinstance(apps, list) or any(not isinstance(app, dict) for app in apps):
        raise ValueError("Invalid Function App inventory response.")
    matches = [app for app in apps if str(app.get("resourceGroup", "")).casefold() == group.casefold() and
               (app.get("name", "").casefold() == outputs["functionAppName"].casefold()
                if outputs.get("functionAppName") else
                app.get("tags", {}).get("azd-env-name") == outputs["AZURE_ENV_NAME"] and
                app.get("tags", {}).get("azd-service-name") == "function-app")]
    if len(matches) > 1:
        raise ValueError("Ambiguous Function App inventory response.")
    exists = bool(matches)
    run("azd", "env", "set", "PLANNER_FUNCTION_APP_EXISTS", str(exists).lower())
    return exists


def validate_selection(items):
    """Require exact reviewed wire keys, real IDs and distinct supported events."""
    if not isinstance(items, list) or not items:
        raise ValueError("Select at least one Planner trigger.")
    seen = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"functionName", "operationName", "parameters"}:
            raise ValueError("Invalid trigger input fields.")
        function = item["functionName"]
        if not isinstance(function, str) or function not in OPERATIONS or function in seen:
            raise ValueError("Select distinct supported Planner functions.")
        seen.add(function)
        operation, keys = OPERATIONS[function]
        if item["operationName"] != operation or not isinstance(item["parameters"], list):
            raise ValueError("Function and operation do not match the reviewed contract.")
        names = []
        for parameter in item["parameters"]:
            if not isinstance(parameter, dict) or set(parameter) != {"name", "value"}:
                raise ValueError("Invalid parameter fields.")
            name, value = parameter["name"], parameter["value"]
            if (not isinstance(name, str) or not isinstance(value, str) or not value.strip() or
                    value != value.strip() or any(character in value for character in "<>\r\n") or
                    value.casefold() in {"todo", "changeme", "placeholder", "group-id", "plan-id"}):
                raise ValueError("Supply actual non-empty Planner identifiers, not placeholders.")
            names.append(name)
        if len(names) != len(set(names)) or set(names) != set(keys):
            raise ValueError("Planner parameters must match the reviewed required wire keys.")
    return copy.deepcopy(items)


def select_inputs(project, inputs=None, prompt=input):
    """Use a local file, environment JSON or explicit prompts, without a fake picker."""
    contract = json.loads((project / "infra/triggers.json").read_text(encoding="utf-8"))
    if contract != [{"functionName": name, "operationName": operation, "requiredParameters": list(keys)}
                    for name, (operation, keys) in OPERATIONS.items()]:
        raise ValueError("The local reviewed Planner contract has changed.")
    configured = inputs or project / "trigger-inputs.json"
    if configured.exists():
        return validate_selection(json.loads(configured.read_text(encoding="utf-8")))
    if inputs:
        raise ValueError("The requested trigger input file does not exist.")
    if os.environ.get("PLANNER_TRIGGER_INPUTS"):
        return validate_selection(json.loads(os.environ["PLANNER_TRIGGER_INPUTS"]))
    selected = []
    for function, (operation, keys) in OPERATIONS.items():
        answer = prompt(f"Configure {function}? [y/N]: ").strip().casefold()
        if answer not in ("", "n", "no", "y", "yes"):
            raise ValueError("Answer yes or no; no sources have changed.")
        if answer not in ("y", "yes"):
            continue
        parameters = []
        for name in keys:
            setting = "PLANNER_GROUP_ID" if name == "groupId" else "PLANNER_PLAN_ID"
            value = os.environ.get(setting) or prompt(f"Actual {name} (id means plan ID, not task ID): ").strip()
            parameters.append({"name": name, "value": value})
        selected.append({"functionName": function, "operationName": operation, "parameters": parameters})
    return validate_selection(selected)


def polling_endpoint(receive_uri, name):
    """Accept only a service HTTPS receive URI for the expected trigger."""
    if not isinstance(receive_uri, str):
        raise ValueError("The service did not return a polling receive URI.")
    parsed = urlsplit(receive_uri)
    marker = "/triggerconfigs/"
    path = unquote(parsed.path)
    index = path.casefold().find(marker)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or
            parsed.fragment or parsed.port not in (None, 443) or index <= 0 or
            path[index + len(marker):].casefold() != (name + "/receive").casefold() or
            parsed.hostname.casefold() in {"localhost", "example.com", "example.invalid"}):
        raise ValueError("Invalid service polling receive URI.")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("A service DNS hostname is required.")
    prefix = parsed.path[:parsed.path.casefold().index(marker)]
    if any(segment in {".", ".."} for segment in unquote(prefix).split("/")):
        raise ValueError("Invalid polling gateway path.")
    if prefix.casefold().endswith("/api"):
        prefix = prefix[:-4]
    return f"https://{parsed.netloc}{prefix}"


class Setup:
    """Keep every Azure call pinned to one subscription and verify ownership first."""

    def __init__(self, outputs, mode, run=None, wait=time.sleep):
        required(outputs, "AZURE_SUBSCRIPTION_ID", "resourceGroupName", "functionAppName",
                 "connectorNamespaceName", "connectorNamespaceConnectionName")
        if mode not in {"polling", "webhook"}:
            raise ValueError("Invalid delivery mode.")
        if mode == "webhook":
            required(outputs, "functionAppDefaultHostname")
        self.outputs, self.mode, self.run, self.wait = outputs, mode, run or cli, wait
        self.collection = ("https://management.azure.com/subscriptions/" + quote(outputs["AZURE_SUBSCRIPTION_ID"], safe="") +
                           "/resourceGroups/" + quote(outputs["resourceGroupName"], safe="") +
                           "/providers/Microsoft.Web/connectorGateways/" + quote(outputs["connectorNamespaceName"], safe="") +
                           "/triggerConfigs")

    def az(self, *arguments, interactive=False):
        return self.run("az", *arguments, "--subscription", self.outputs["AZURE_SUBSCRIPTION_ID"], interactive=interactive)

    def rest(self, method, url, properties=None):
        if properties is None:
            return self.az("rest", "--method", method, "--url", url, "-o", "json")
        with private_json({"properties": properties}) as body:
            return self.az("rest", "--method", method, "--url", url, "--body", body, "-o", "json")

    def authorize(self):
        arguments = ("-g", self.outputs["resourceGroupName"], "--namespace", self.outputs["connectorNamespaceName"],
                     "--connection-name", self.outputs["connectorNamespaceConnectionName"])

        def connected():
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

    def list_triggers(self):
        target, visited, resources = urlsplit(self.collection), set(), []
        url = self.collection + "?api-version=" + API_VERSION
        while url:
            if not isinstance(url, str):
                raise ValueError("Invalid continuation URL.")
            parsed = urlsplit(url)
            if (parsed.scheme != target.scheme or parsed.netloc != target.netloc or parsed.fragment or
                    parsed.path.rstrip("/").casefold() != target.path.casefold() or url in visited or len(visited) >= 100):
                raise ValueError("Invalid, repeated or excessive trigger continuation URL.")
            visited.add(url)
            page = self.rest("get", url)
            if (not isinstance(page, dict) or not isinstance(page.get("value"), list) or
                    any(not isinstance(item, dict) for item in page["value"])):
                raise ValueError("Invalid trigger collection response.")
            resources.extend(page["value"])
            url = page.get("nextLink")
        return resources

    def name(self, function):
        return self.outputs["connectorNamespaceConnectionName"] + "-" + self.mode + "-" + function.lower()

    def metadata(self, function):
        return {"sample": "planner-python", "deliveryMode": self.mode, "destinationType": "functionApp",
                "functionAppSubscriptionId": self.outputs["AZURE_SUBSCRIPTION_ID"],
                "functionAppResourceGroup": self.outputs["resourceGroupName"],
                "functionAppName": self.outputs["functionAppName"], "functionName": function}

    def owned(self, resource, function):
        name = self.name(function)
        properties = resource.get("properties") if isinstance(resource, dict) else None
        modes = {"Poll"} if self.mode == "polling" else {None, "", "Webhook", "Push", "NotSpecified"}
        if (not isinstance(properties, dict) or
                resource.get("id", "").casefold() != (urlsplit(self.collection).path + "/" + name).casefold() or
                resource.get("name", "").casefold() != name.casefold() or
                properties.get("operationName") != OPERATIONS[function][0] or
                properties.get("connectionDetails", {}).get("connectionName") != self.outputs["connectorNamespaceConnectionName"] or
                properties.get("connectionDetails", {}).get("connectorName") != "planner" or
                properties.get("deliveryMode") not in modes or
                any(properties.get("metadata", {}).get(key) != value for key, value in self.metadata(function).items())):
            raise ValueError("Refusing to change a trigger whose ownership does not match this app and mode.")
        return properties

    def settings(self, values):
        arguments = ("-g", self.outputs["resourceGroupName"], "-n", self.outputs["functionAppName"])
        with private_json(values) as path:
            self.az("functionapp", "config", "appsettings", "set", *arguments, "--settings", path, "-o", "none")
        response = self.az("functionapp", "config", "appsettings", "list", *arguments, "-o", "json")
        if not isinstance(response, list):
            raise ValueError("Could not verify app settings.")
        actual = {item["name"]: item["value"] for item in response}
        if any(actual.get(name) != value for name, value in values.items()):
            raise ValueError("App settings verification failed; output withheld.")

    def configure(self, selection, *, sources_only=False, app_exists=True):
        """Preflight all sources; disable old listeners; enable only verified sources."""
        selected = {item["functionName"]: item for item in validate_selection(selection)}
        self.authorize()
        resources, existing = self.list_triggers(), {}
        urls = {function: self.collection + "/" + quote(self.name(function), safe="") + "?api-version=" + API_VERSION
                for function in OPERATIONS}
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
                existing[function] = self.rest("get", urls[function])
                self.owned(existing[function], function)
        callback = None
        if self.mode == "webhook":
            hostname = self.outputs["functionAppDefaultHostname"]
            parsed = urlsplit("https://" + hostname)
            if parsed.netloc != hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.port:
                raise ValueError("Invalid actual Function App hostname.")
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
            callback = {"httpMethod": "Post", "callbackUrl": "https://" + hostname + "/runtime/webhooks/connector?functionName=",
                        "authentication": {"type": "QueryString", "name": "code", "value": key}}
        values = {"PYTHON_ISOLATE_WORKER_DEPENDENCIES": "1", "ConnectorNamespace__credential": "managedidentity"}
        disabled = {f"AzureWebJobs.{function}.Disabled": "true" for function in OPERATIONS}
        values.update(disabled)
        if self.mode == "polling":
            values.update({function + "TriggerConfigName": self.name(function) for function in OPERATIONS})
        if app_exists:
            self.settings(disabled)
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
                        dict(callback, callbackUrl=callback["callbackUrl"] + function))
            unchanged = resource is not None and resource["properties"].get("provisioningState") == "Succeeded" and all(
                resource["properties"].get(key) == value for key, value in properties.items())
            if not unchanged:
                self.rest("put", urls[function], properties)
            for attempt in range(30):
                current = self.rest("get", urls[function])
                verified = self.owned(current, function)
                if verified.get("provisioningState") in {"Failed", "Canceled", "Cancelled"}:
                    raise ValueError("Planner source registration failed; listeners remain disabled.")
                ready = verified.get("provisioningState") == "Succeeded" and all(
                    verified.get(key) == value for key, value in properties.items())
                if ready and (self.mode != "polling" or function not in selected or
                              verified.get("pollingEndpoints", {}).get("receiveUri")):
                    break
                if attempt == 29:
                    raise TimeoutError("Planner source readiness timed out; listeners remain disabled.")
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
        values.update({f"AzureWebJobs.{function}.Disabled": str(function not in selected).lower() for function in OPERATIONS})
        if not sources_only:
            try:
                self.settings(values)
            except (ValueError, RuntimeError, OSError):
                try:
                    self.settings(disabled)
                except (ValueError, RuntimeError, OSError):
                    raise RuntimeError("Settings verification and rollback failed; manually disable this app.") from None
                raise
        print(f"Verified {len(selected)} Planner {self.mode} sources.")
        return values


def main(argv=None):
    """Run explicit phases; importing the helper never calls Azure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("polling", "webhook"), required=True)
    parser.add_argument("--phase", choices=("sources", "detect", "local", "configure"), default="configure")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--inputs", type=Path, default=os.environ.get("PLANNER_INPUTS_FILE"))
    parser.add_argument("--force", action="store_true")
    options = parser.parse_args(argv)
    outputs = cli("azd", "env", "get-values", "--output", "json")
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd environment outputs.")
    if options.phase == "detect":
        detect_app(outputs)
        return
    project = options.project.resolve()
    regular_file(project / "local.settings.json")
    if options.phase == "local":
        if options.mode != "polling":
            raise ValueError("Only polling has a local-settings-only phase.")
        required(outputs, "connectorPollingEndpoint", "triggerConfigSettingsEncoded")
        values = json.loads(base64.b64decode(outputs["triggerConfigSettingsEncoded"], validate=True))
        if not isinstance(values, dict) or any(not isinstance(value, str) for value in values.values()):
            raise ValueError("Invalid listener settings output.")
        values["ConnectorNamespace__pollingEndpoint"] = outputs["connectorPollingEndpoint"]
    else:
        if options.phase == "sources" and options.mode != "polling":
            raise ValueError("Only polling creates sources before the app.")
        selection = select_inputs(project, options.inputs)
        setup = Setup(outputs, options.mode)
        exists = detect_app(outputs) if options.phase == "sources" else True
        values = setup.configure(selection, sources_only=options.phase == "sources", app_exists=exists)
        if options.phase == "sources":
            cli("azd", "env", "set", "PLANNER_POLLING_ENDPOINT", values.pop("ConnectorNamespace__pollingEndpoint"))
            values.pop("ConnectorNamespace__credential", None)
            encoded = base64.b64encode(json.dumps(values).encode()).decode()
            cli("azd", "env", "set", "PLANNER_LISTENER_SETTINGS_ENCODED", encoded)
            return
    values.pop("ConnectorNamespace__credential", None)
    values.update(AzureWebJobsStorage="UseDevelopmentStorage=true", FUNCTIONS_WORKER_RUNTIME="python",
                  PYTHON_ISOLATE_WORKER_DEPENDENCIES="1")
    write_local_settings(project / "local.settings.json", values, force=options.force)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, EOFError, subprocess.SubprocessError):
        print("Planner setup failed. Check consent, inputs, ownership and service readiness; details withheld.", file=sys.stderr)
        sys.exit(1)