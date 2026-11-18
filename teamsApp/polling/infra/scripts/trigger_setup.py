# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Deployment-time trigger selection for this standalone connector sample."""

import argparse
import base64
import copy
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit

from trigger_inputs import choose_from_terminal, collect_trigger_inputs, make_picker

API_VERSION = "2026-05-01-preview"
READ_ONLY = {"pollingEndpoints", "provisioningState", "statuses", "overallStatus", "createdTime", "changedTime"}


def cli(program, *arguments, interactive=False):
    executable = (shutil.which(program + ".cmd") if os.name == "nt" else None) or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is unavailable.")
    result = subprocess.run([executable, *arguments], capture_output=not interactive, text=True,
                            encoding="utf-8", timeout=660 if interactive else 120, check=False)
    if result.returncode:
        raise RuntimeError(f"'{program}' failed; command arguments and response bodies were not logged.")
    return json.loads(result.stdout) if not interactive and result.stdout.strip() else None


@contextmanager
def private_json(value):
    directory = Path(tempfile.mkdtemp(prefix="connector-trigger-"))
    try:
        if os.name == "nt":
            identity = subprocess.run(["whoami.exe", "/user", "/fo", "csv", "/nh"],
                                      capture_output=True, text=True, check=True)
            sid = next(csv.reader([identity.stdout.strip()]))[1]
            subprocess.run(["icacls.exe", str(directory), "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F",
                            "/remove:g", "*S-1-3-4", "*S-1-5-18", "*S-1-5-32-544"],
                           capture_output=True, check=True)
        else:
            directory.chmod(0o700)
        path = directory / "request.json"
        with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w", encoding="utf-8") as stream:
            json.dump(value, stream)
        yield "@" + str(path)
    finally:
        shutil.rmtree(directory)


def encode(value):
    return base64.b64encode(json.dumps(value).encode()).decode()


def validate_selection(selected, definitions):
    supported = {item["functionName"]: item["operationName"] for item in definitions}
    if not isinstance(selected, list) or not selected:
        raise ValueError("Select at least one trigger.")
    seen = set()
    for item in selected:
        if not isinstance(item, dict) or set(item) != {"functionName", "operationName", "parameters"}:
            raise ValueError("Invalid trigger input fields.")
        name = item["functionName"]
        if not isinstance(name, str) or name in seen or name not in supported or item["operationName"] != supported[name]:
            raise ValueError("Select distinct supported function/operation pairs.")
        seen.add(name)
        parameters = item["parameters"]
        if not isinstance(parameters, list):
            raise ValueError("Trigger parameters must be an array.")
        names = set()
        for parameter in parameters:
            if (not isinstance(parameter, dict) or set(parameter) != {"name", "value"}
                    or not isinstance(parameter["name"], str) or not parameter["name"]
                    or parameter["name"] in names or parameter["value"] is None):
                raise ValueError("Invalid or duplicate trigger parameters.")
            names.add(parameter["name"])
    return copy.deepcopy(selected)


def polling_endpoint(uri):
    parsed = urlsplit(uri)
    match = re.fullmatch(r"(.*)/triggerconfigs/[^/]+/receive/?", parsed.path, re.IGNORECASE)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or parsed.port not in (None, 443) or not match):
        raise ValueError("The service returned an invalid polling receive URI.")
    prefix = match[1]
    if prefix.lower() == "/api":
        prefix = ""
    elif prefix and not re.fullmatch(r"/api/connectorGateways/[^/]+", prefix, re.IGNORECASE):
        raise ValueError("The service returned an unsupported polling endpoint path.")
    return f"https://{parsed.netloc}{prefix}"


class Setup:
    def __init__(self, project, config, outputs, *, run=cli, prompt=input, wait=time.sleep):
        self.project, self.config, self.outputs = project, config, outputs
        self.run, self.prompt, self.wait = run, prompt, wait
        self.choose = choose_from_terminal(prompt)
        self.mode = "Poll" if project.name == "polling" else "Webhook"
        for name in ("AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName",
                     "connectorNamespaceConnectionName", "functionAppName"):
            if not isinstance(outputs.get(name), str) or not outputs[name].strip():
                raise ValueError(f"Missing deployment output {name}.")
        self.root = ("https://management.azure.com/subscriptions/" + outputs["AZURE_SUBSCRIPTION_ID"]
                     + "/resourceGroups/" + outputs["resourceGroupName"]
                     + "/providers/Microsoft.Web/connectorGateways/" + outputs["connectorNamespaceName"])
        self.connection = self.root + "/connections/" + quote(outputs["connectorNamespaceConnectionName"], safe="")
        self.collection = self.root + "/triggerConfigs"

    def rest(self, method, url, body=None):
        arguments = ["rest", "--method", method, "--url",
                     url if "?" in url else url + "?api-version=" + API_VERSION,
                     "--subscription", self.outputs["AZURE_SUBSCRIPTION_ID"], "-o", "json"]
        if body is None:
            return self.run("az", *arguments)
        with private_json(body) as path:
            return self.run("az", *arguments, "--body", path)

    def authorize(self):
        connection = self.rest("GET", self.connection)
        if connection.get("properties", {}).get("connectorName") != self.config["connectorName"]:
            raise ValueError("The connection does not match this sample's connector.")
        if connection["properties"].get("overallStatus", "").lower() != "connected":
            self.run("az", "connector-namespace", "connection", "authenticate",
                     "-g", self.outputs["resourceGroupName"], "--namespace", self.outputs["connectorNamespaceName"],
                     "--connection-name", self.outputs["connectorNamespaceConnectionName"],
                     "--subscription", self.outputs["AZURE_SUBSCRIPTION_ID"], "--timeout", "300",
                     "--no-access-policy", interactive=True)
            connection = self.rest("GET", self.connection)
        if connection.get("properties", {}).get("overallStatus", "").lower() != "connected":
            raise ValueError("The connector connection is not authorized.")

    def select(self, path=None):
        configured = path or self.project / "trigger-inputs.json"
        setting = "POLLING_TRIGGER_INPUTS" if self.mode == "Poll" else "WEBHOOK_TRIGGER_INPUTS"
        if configured.exists():
            return validate_selection(json.loads(configured.read_text(encoding="utf-8")), self.config["triggers"])
        if path:
            raise ValueError("The requested trigger input file does not exist.")
        if self.outputs.get(setting):
            return validate_selection(json.loads(base64.b64decode(self.outputs[setting], validate=True)),
                                      self.config["triggers"])
        if self.config["connectorName"] == "onedriveforbusiness":
            selected = [definition for definition in self.config["triggers"]
                        if self.choose(f"Configure {definition['functionName']}?", [("Skip", False), ("Configure", True)])]
            if not selected:
                raise ValueError("Select at least one trigger.")
            folder_id = os.environ.get("ONEDRIVE_FOLDER_ID") or self.outputs.get("ONEDRIVE_FOLDER_ID") or self.select_folder()
            if not folder_id.strip() or folder_id.strip().lower() in {"root", "null"}:
                raise ValueError("Use a connector-returned OneDrive folder ID, not a path or literal root.")
            return [{"functionName": item["functionName"], "operationName": item["operationName"],
                     "parameters": [{"name": "folderId", "value": folder_id}]} for item in selected]
        location = self.outputs.get("CONNECTOR_NAMESPACE_LOCATION", "westcentralus")
        exported = self.rest("GET", "https://management.azure.com/subscriptions/" + self.outputs["AZURE_SUBSCRIPTION_ID"]
                             + "/providers/Microsoft.Web/locations/" + quote(location, safe="")
                             + "/managedApis/" + self.config["connectorName"] + "?api-version=2016-06-01&export=true")
        swagger = exported.get("properties", {}).get("apiDefinitions", {}).get("value", exported)
        if isinstance(swagger, str):
            swagger = json.loads(swagger)
        definitions = copy.deepcopy(self.config["triggers"])
        for definition in definitions:
            values = definition.setdefault("values", {})
            for name, setting_name in definition.pop("environment", {}).items():
                value = os.environ.get(setting_name) or self.outputs.get(setting_name)
                if value:
                    target = values
                    keys = name.split("/")
                    for key in keys[:-1]:
                        target = target.setdefault(key, {})
                    target[keys[-1]] = value
        picker = make_picker(swagger, lambda body: self.rest("POST", self.connection + "/dynamicInvoke", body))
        return validate_selection(collect_trigger_inputs(swagger, definitions, picker, choose=self.choose, prompt=self.prompt),
                                  self.config["triggers"])

    def select_folder(self):
        stack = []
        while True:
            current = stack[-1] if stack else None
            path = "/datasets/default/folders" + ("/" + quote(current["Id"], safe="") if current else "")
            response = self.rest("POST", self.connection + "/dynamicInvoke", {"request": {"method": "GET", "path": path}}).get("response", {})
            if str(response.get("statusCode")).upper() not in {"200", "OK"}:
                raise ValueError("OneDrive folder listing failed.")
            body = response.get("body")
            body = json.loads(body) if isinstance(body, str) else body
            items = body if isinstance(body, list) else body.get("value")
            if not isinstance(items, list):
                raise ValueError("Invalid OneDrive folder listing.")
            choices = ([("Use " + (current.get("Name") or current["Id"]), "select"), ("Parent folder", "up")]
                       if current else [("Use the top-level folder", "root")])
            choices.extend((item.get("Name") or item["Id"], item) for item in items
                           if item.get("IsFolder") is True and item.get("Id") not in {None, "", "root"})
            chosen = self.choose("Select the OneDrive folder to monitor", choices)
            if chosen == "select":
                return current["Id"]
            if chosen == "root":
                response = self.rest("POST", self.connection + "/dynamicInvoke", {
                    "request": {"method": "GET", "path": "/datasets/default/GetFileByPath", "queries": {"path": "/"}},
                }).get("response", {})
                if str(response.get("statusCode")).upper() not in {"200", "OK"}:
                    raise ValueError("Could not resolve the OneDrive top-level folder ID.")
                body = response.get("body")
                body = json.loads(body) if isinstance(body, str) else body
                if not isinstance(body, dict) or not isinstance(body.get("Id"), str):
                    raise ValueError("The connector did not return a OneDrive folder ID.")
                return body["Id"]
            if chosen == "up":
                stack.pop()
            else:
                stack.append(chosen)

    def inventory(self):
        resources, visited = {}, set()
        page = self.collection
        while page:
            if len(visited) >= 100 or page in visited or (page != self.collection and not page.startswith(self.collection + "?")):
                raise ValueError("Unsafe or cyclic trigger inventory continuation.")
            visited.add(page)
            result = self.rest("GET", page)
            if not isinstance(result.get("value"), list):
                raise ValueError("Invalid trigger inventory.")
            for resource in result["value"]:
                name = resource.get("name")
                if not isinstance(name, str) or name.lower() in resources:
                    raise ValueError("Ambiguous trigger inventory.")
                resources[name.lower()] = resource
            page = result.get("nextLink")
        return resources

    def name(self, definition):
        prefix = self.config["namePrefix"] if self.mode == "Poll" else self.outputs["connectorNamespaceConnectionName"]
        return prefix + "-" + definition["functionName"].lower()

    def properties(self, definition, parameters):
        return {
            "connectionDetails": {"connectorName": self.config["connectorName"],
                                  "connectionName": self.outputs["connectorNamespaceConnectionName"]},
            **({"deliveryMode": "Poll"} if self.mode == "Poll" else {}),
            "operationName": definition["operationName"], "parameters": parameters,
            "state": "Enabled", "type": "NotSpecified",
            "metadata": {"destinationType": "functionApp", "functionAppSubscriptionId": self.outputs["AZURE_SUBSCRIPTION_ID"],
                         "functionAppResourceGroup": self.outputs["resourceGroupName"],
                         "functionAppName": self.outputs["functionAppName"], "functionName": definition["functionName"]},
        }

    def owned(self, resource, definition):
        expected = self.properties(definition, [])
        properties = resource.get("properties", {})
        if (resource.get("name") != self.name(definition)
                or resource.get("id", "").lower() != (self.collection + "/" + self.name(definition))[len("https://management.azure.com"):].lower()
                or any(properties.get("connectionDetails", {}).get(key) != value
                       for key, value in expected["connectionDetails"].items())
                or properties.get("operationName") != expected["operationName"]
                or any(properties.get("metadata", {}).get(key) != value for key, value in expected["metadata"].items())
                or (properties.get("deliveryMode") == "Poll") != (self.mode == "Poll")):
            raise ValueError("Refusing to overwrite an unowned trigger configuration.")
        if self.mode == "Webhook":
            callback = urlsplit(properties.get("notificationDetails", {}).get("callbackUrl", ""))
            allowed = {"https://" + self.outputs.get("functionAppDefaultHostname", "")}
            if (callback.scheme != "https" or f"https://{callback.netloc}" not in allowed
                    or callback.port not in (None, 443)
                    or callback.username or callback.password or callback.fragment
                    or callback.path != "/runtime/webhooks/connector"
                    or callback.query not in {"functionName=" + definition["functionName"], "functionName=*sanitized*"}):
                raise ValueError("Refusing to change another application's callback.")

    def matches(self, resource, parameters):
        properties = (resource or {}).get("properties", {})
        return (properties.get("state") == "Enabled"
                and properties.get("provisioningState") not in {"Failed", "Canceled", "Cancelled"}
                and sorted(properties.get("parameters", []), key=lambda item: item["name"])
                == sorted(parameters, key=lambda item: item["name"])
                and (self.mode != "Poll" or bool(properties.get("pollingEndpoints", {}).get("receiveUri"))))

    def guard(self, definition, parameters, resource, *, journal=True):
        if self.config["connectorName"] != "commondataservice":
            return
        if resource and sorted(resource["properties"]["parameters"], key=lambda item: item["name"]) != sorted(parameters, key=lambda item: item["name"]):
            raise ValueError("Dataverse source selectors changed. Explicitly clean up the existing source subscription first.")
        if resource and self.mode == "Webhook" and resource["properties"].get("state") != "Enabled":
            raise ValueError("Inspect the disabled Dataverse source subscription before enabling it again.")
        if journal and definition["operationName"] == "BusinessEventsTrigger":
            with private_json({"outputs": self.outputs, "parameters": parameters, "resource": resource, "mode": self.mode}) as path:
                self.run("pwsh", "-NoProfile", "-File", str(self.project / "infra/scripts/guard-action.ps1"), path[1:])

    def settings(self, selected):
        names = {item["functionName"] for item in selected}
        settings = {}
        for definition in self.config["triggers"]:
            function = definition["functionName"]
            settings[f"AzureWebJobs.{function}.Disabled"] = str(function not in names).lower()
            if self.mode == "Poll":
                settings[function + "TriggerConfigName"] = self.name(definition)
        return settings

    def save_settings(self, settings):
        with private_json(settings) as path:
            self.run("az", "functionapp", "config", "appsettings", "set", "-g", self.outputs["resourceGroupName"],
                     "-n", self.outputs["functionAppName"], "--subscription", self.outputs["AZURE_SUBSCRIPTION_ID"],
                     "--settings", path, "-o", "none")

    def configure(self, selected):
        validate_selection(selected, self.config["triggers"])
        if self.config["connectorName"] == "onedriveforbusiness":
            for trigger in selected:
                folder = next((item["value"] for item in trigger["parameters"] if item["name"] == "folderId"), None)
                if (not isinstance(folder, str) or not folder.strip() or folder.startswith("/")
                        or folder.strip().lower() in {"root", "null"}):
                    raise ValueError("Use a connector-returned OneDrive folder ID, not a path or literal root.")
        inventory = self.inventory()
        selections = {item["functionName"]: item for item in selected}
        plan = []
        for definition in self.config["triggers"]:
            resource = inventory.get(self.name(definition).lower())
            if resource:
                self.owned(resource, definition)
            trigger = selections.get(definition["functionName"])
            if trigger:
                self.guard(definition, trigger["parameters"], resource, journal=False)
            plan.append((definition, trigger, resource))
        for definition, trigger, resource in plan:
            if trigger:
                self.guard(definition, trigger["parameters"], resource)
        if self.mode == "Webhook":
            self.save_settings({f"AzureWebJobs.{definition['functionName']}.Disabled": "true"
                                for definition in self.config["triggers"]})
            app = self.rest("GET", "https://management.azure.com/subscriptions/" + self.outputs["AZURE_SUBSCRIPTION_ID"]
                            + "/resourceGroups/" + self.outputs["resourceGroupName"]
                            + "/providers/Microsoft.Web/sites/" + self.outputs["functionAppName"])
            if app.get("properties", {}).get("defaultHostName") != self.outputs.get("functionAppDefaultHostname"):
                raise ValueError("Actual Function App hostname differs from deployment outputs.")
            key = self.run(
                "az", "functionapp", "keys", "list", "-g", self.outputs["resourceGroupName"],
                "-n", self.outputs["functionAppName"], "--subscription", self.outputs["AZURE_SUBSCRIPTION_ID"],
                "-o", "json").get("systemKeys", {}).get("connector_extension")
            if not isinstance(key, str) or not key:
                raise ValueError("The connector extension system key is unavailable.")
        changed = []
        for definition, trigger, resource in plan:
            url = self.collection + "/" + self.name(definition)
            if not trigger:
                if resource and resource["properties"].get("state") != "Disabled":
                    properties = {key: value for key, value in resource["properties"].items() if key not in READ_ONLY}
                    self.rest("PUT", url, {"properties": {**properties, "state": "Disabled"}})
                    if self.rest("GET", url)["properties"].get("state") != "Disabled":
                        raise ValueError("A skipped trigger could not be disabled.")
                continue
            if self.matches(resource, trigger["parameters"]):
                if self.mode == "Poll" or self.config["connectorName"] == "commondataservice":
                    continue
            previous = (resource or {}).get("properties", {})
            desired = self.properties(definition, trigger["parameters"])
            properties = {**{key: value for key, value in previous.items() if key not in READ_ONLY}, **desired,
                          "metadata": {**previous.get("metadata", {}), **desired["metadata"]}}
            if self.mode == "Poll":
                changed.append({"name": self.name(definition), "properties": properties})
            else:
                properties["notificationDetails"] = {**previous.get("notificationDetails", {}),
                    "callbackUrl": "https://" + self.outputs["functionAppDefaultHostname"]
                                   + "/runtime/webhooks/connector?functionName=" + definition["functionName"],
                    "httpMethod": "Post", "authentication": {"type": "QueryString", "name": "code", "value": key},
                }
                self.rest("PUT", url, {"properties": properties})
        settings = self.settings(selected)
        setting = "POLLING_TRIGGER_INPUTS" if self.mode == "Poll" else "WEBHOOK_TRIGGER_INPUTS"
        if self.mode == "Poll":
            first = next(definition for definition in self.config["triggers"] if definition["functionName"] in selections)
            document = {"selected": changed, "settings": settings, "endpointConfigName": self.name(first),
                        **({"revision": str(uuid.uuid4())} if changed else {})}
            self.run("azd", "env", "set", "POLLING_TRIGGER_PLAN", encode(document))
        else:
            self.verify(selected)
            self.save_settings(settings)
        self.run("azd", "env", "set", setting, encode(selected))
        return settings

    def verify(self, selected):
        endpoint = None
        for trigger in selected:
            definition = next(item for item in self.config["triggers"] if item["functionName"] == trigger["functionName"])
            for attempt in range(30):
                resource = self.rest("GET", self.collection + "/" + self.name(definition))
                self.owned(resource, definition)
                if self.matches(resource, trigger["parameters"]):
                    break
                if resource["properties"].get("provisioningState") in {"Failed", "Canceled", "Cancelled"} or attempt == 29:
                    raise ValueError("Selected trigger provisioning failed or timed out.")
                self.wait(2)
            if self.mode == "Poll":
                resolved = polling_endpoint(resource["properties"]["pollingEndpoints"]["receiveUri"])
                if endpoint and endpoint != resolved:
                    raise ValueError("Selected triggers returned inconsistent polling endpoints.")
                endpoint = resolved
            if self.mode == "Webhook" and self.config["connectorName"] == "commondataservice":
                status = self.rest("GET", self.collection + "/" + self.name(definition) + "/triggerStatuses/latest")
                if status.get("lastExecutionStatus") == "Failed" or status.get("lastExecutionError"):
                    raise ValueError("Dataverse source execution failed. Inspect its Connector Namespace trigger status.")
        return endpoint

    def write_local(self, settings, force=False):
        path = self.project / "local.settings.json"
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Local settings must be a regular file.")
        if path.exists() and not force:
            print("Existing local.settings.json preserved.")
            return
        example = json.loads((self.project / "local.settings.example.json").read_text(encoding="utf-8"))
        example["Values"].update(settings)
        with private_json(example) as source:
            descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | (os.O_TRUNC if force else os.O_EXCL), 0o600)
            with open(source[1:], "rb") as stream, os.fdopen(descriptor, "wb") as target:
                shutil.copyfileobj(stream, target)
            path.chmod(0o600)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "verify", "finish", "webhook"))
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--force-local-settings", action="store_true")
    options = parser.parse_args(argv)
    project = Path(__file__).resolve().parents[2]
    config = json.loads((Path(__file__).with_name("trigger-config.json")).read_text(encoding="utf-8"))
    outputs = cli("azd", "env", "get-values", "--output", "json")
    setup = Setup(project, config, outputs)
    if (options.phase == "webhook") != (setup.mode == "Webhook"):
        raise ValueError("Setup phase does not match the sample delivery mode.")
    if options.phase in {"prepare", "webhook"}:
        setup.authorize()
        selected = setup.select(options.inputs)
        settings = setup.configure(selected)
    else:
        selected = setup.select(options.inputs)
        settings = setup.settings(selected)
        endpoint = setup.verify(selected)
        if outputs.get("connectorPollingEndpoint") != endpoint:
            raise ValueError("Polling endpoint differs from the trigger deployment output.")
        settings["ConnectorNamespace__pollingEndpoint"] = endpoint
    if options.phase == "verify":
        apps = cli("az", "functionapp", "list", "-g", outputs["resourceGroupName"],
                   "--subscription", outputs["AZURE_SUBSCRIPTION_ID"], "-o", "json")
        exists = any(app["name"].lower() == outputs["functionAppName"].lower() for app in apps)
        cli("azd", "env", "set", "POLLING_FUNCTION_APP_EXISTS", str(exists).lower())
    if options.phase in {"finish", "webhook"}:
        setup.write_local(settings, options.force_local_settings)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, EOFError) as error:
        print(f"Trigger setup failed: {error}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, TypeError, OSError, subprocess.SubprocessError):
        print("Trigger setup failed. Check connection permissions, selected inputs, and deployment status; sensitive output withheld.",
              file=sys.stderr)
        sys.exit(1)
