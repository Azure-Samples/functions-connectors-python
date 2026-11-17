# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Offline regression tests. Run with unittest discovery; no Azure command executes."""

import base64
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import List, get_args
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def load(mode, filename):
    """Import actual mode-local code without invoking its CLI entry point."""
    spec = importlib.util.spec_from_file_location("vsts_" + mode + filename.stem, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HELPERS = {mode: load(mode, ROOT / mode / "infra/scripts/setup.py") for mode in ("polling", "webhook")}


class Service:
    """In-memory ARM and CLI boundary with real private request-file reads."""

    def __init__(self, mode):
        self.mode = mode
        self.helper = HELPERS[mode]
        self.outputs = {
            "AZURE_SUBSCRIPTION_ID": "subscription", "AZURE_ENV_NAME": "review",
            "resourceGroupName": "rg-review", "functionAppName": "func-review",
            "connectorNamespaceName": "cn-review", "connectorNamespaceConnectionName": "vsts-review-entra",
            "connectorNamespaceResourceId": "/subscriptions/subscription/resourceGroups/rg-review/providers/Microsoft.Web/connectorGateways/cn-review",
            "CONNECTOR_NAMESPACE_LOCATION": "brazilsouth", "deliveryMode": mode,
        }
        if mode == "webhook":
            self.outputs["FUNCTION_APP_HOSTNAME"] = "func-review.azurewebsites.net"
        self.ctx = self.helper.context(self.outputs, mode)
        self.swagger = {"paths": {"/" + operation: {"get": {
            "operationId": operation,
            "parameters": [{"name": name, "in": "query", "type": "string", "required": True, "minLength": 1}
                           for name in self.helper.REQUIRED_PARAMETERS[operation]]
                          + [{"name": "filter", "in": "query", "type": "string", "pattern": "^[a-z]+$"}],
        }} for operation in self.helper.OPERATIONS.values()}}
        self.connected = False
        self.resources = {}
        self.events = []
        self.puts = []
        self.settings = {"Unrelated": "keep", "VstsConnection": "old-runtime"}
        self.environment = {}
        self.fail_put = False

    def selected(self, function="OnVstsBuildCompleted"):
        """Return a complete selection with exact wire keys."""
        operation = self.helper.OPERATIONS[function]
        return [{"functionName": function, "operationName": operation,
                 "parameters": [{"name": name, "value": "reviewed"}
                                for name in self.helper.REQUIRED_PARAMETERS[operation]]}]

    def source(self, function, *, owned=True):
        """Build a service-owned response with writable and read-only fields."""
        name = self.outputs["connectorNamespaceConnectionName"] + "-" + function.lower()
        properties = {
            "connectionDetails": {"connectorName": self.helper.CONNECTOR, "connectionName": self.outputs["connectorNamespaceConnectionName"]},
            "operationName": self.helper.OPERATIONS[function], "state": "Enabled",
            "metadata": {**self.helper.metadata(self.outputs, self.ctx, function), "extra": "preserve"},
            "parameters": self.selected(function)[0]["parameters"],
            "recurrence": {"frequency": "Minute", "interval": 1}, "provisioningState": "Succeeded",
        }
        if not owned:
            properties["metadata"]["functionAppName"] = "other-app"
        if self.mode == "polling":
            properties.update(deliveryMode="Poll", pollingEndpoints={"receiveUri": "https://example.logic.azure.com/api/triggerconfigs/" + name + "/receive"})
        return {"id": urlsplit(self.ctx["collection"]).path + "/" + name, "name": name, "properties": properties}

    def run(self, program, arguments, **options):
        """Reject every unexpected call instead of returning an empty success."""
        self.events.append((program, list(arguments), options))
        if program == "azd":
            assert arguments[:2] == ["env", "set"]
            self.environment[arguments[2]] = arguments[3]
            return None
        assert program == "az"
        assert arguments[arguments.index("--subscription") + 1] == "subscription"
        if arguments[:3] == ["connector-namespace", "connection", "authenticate"]:
            assert options == {"interactive": True}
            assert "--no-access-policy" in arguments
            self.connected = True
            return None
        if arguments[:3] == ["functionapp", "keys", "list"]:
            return {"systemKeys": {"connector_extension": "callback-secret"}}
        if arguments[:4] == ["functionapp", "config", "appsettings", "set"]:
            body = json.loads(Path(arguments[arguments.index("--settings") + 1][1:]).read_text())
            self.settings.update(body)
            return None
        assert arguments[0] == "rest"
        method, url = arguments[arguments.index("--method") + 1], arguments[arguments.index("--url") + 1]
        path = urlsplit(url).path
        if path.endswith("/connections/" + self.outputs["connectorNamespaceConnectionName"]):
            assert method == "GET"
            return {"properties": {"parameterValueSet": {"name": "EntraOAuth"},
                                   "overallStatus": "Connected" if self.connected else "Error",
                                   "connectionRuntimeUrl": "https://runtime.logic.azure.com/apim/vsts"}}
        if "/managedApis/" in path:
            assert self.connected, "Swagger/selection must follow consent"
            return self.swagger
        if "/sites/" in path:
            assert self.mode == "webhook", "Poll registration must not require a Function App"
            return {"properties": {"defaultHostName": self.outputs["FUNCTION_APP_HOSTNAME"]}}
        assert path.startswith(urlsplit(self.ctx["collection"]).path)
        if path == urlsplit(self.ctx["collection"]).path:
            assert method == "GET"
            return {"value": list(self.resources.values())}
        name = path.rsplit("/", 1)[1]
        if method == "GET":
            return copy.deepcopy(self.resources[name])
        assert method == "PUT" and self.connected
        assert not self.fail_put, "Injected source registration failure"
        body = json.loads(Path(arguments[arguments.index("--body") + 1][1:]).read_text())
        self.puts.append(copy.deepcopy(body))
        assert not self.helper.READ_ONLY.intersection(body["properties"])
        resource = {"id": path, "name": name, **body}
        resource["properties"]["provisioningState"] = "Succeeded"
        if self.mode == "polling":
            resource["properties"]["pollingEndpoints"] = {"receiveUri": "https://example.logic.azure.com/api/triggerconfigs/" + name + "/receive"}
        self.resources[name] = copy.deepcopy(resource)
        return resource


class SetupTests(unittest.TestCase):
    """Test real reconciliation against a mocked external boundary only."""

    def project(self, directory, mode):
        project = Path(directory).resolve()
        shutil.copyfile(ROOT / mode / "local.settings.example.json", project / "local.settings.example.json")
        return project

    def test_poll_consent_picker_enabled_sources_then_app_outputs(self):
        service = Service("polling")
        answers = iter(["1", "organization", "project", "", "yes"])

        def prompt(message):
            self.assertTrue(service.connected)
            self.assertFalse(service.puts)
            return next(answers)

        with tempfile.TemporaryDirectory() as directory:
            service.helper.setup(service.outputs, None, "polling", Path(directory), run=service.run, prompt=prompt)
            self.assertFalse((Path(directory) / "local.settings.json").exists())
        self.assertEqual(len(service.puts), 1)
        self.assertEqual(service.puts[0]["properties"]["state"], "Enabled")
        self.assertEqual(service.puts[0]["properties"]["deliveryMode"], "Poll")
        settings = json.loads(base64.b64decode(service.environment["triggerConfigSettingsEncoded"]))
        self.assertEqual(settings["AzureWebJobs.OnVstsBuildCompleted.Disabled"], "false")
        self.assertEqual(settings["AzureWebJobs.OnVstsGitPush.Disabled"], "true")
        self.assertEqual(len(settings), 18)
        self.assertEqual(service.environment["connectorPollingEndpoint"], "https://example.logic.azure.com")
        self.assertFalse(any("functionapp" in arguments for _, arguments, _ in service.events))

    def test_interactive_cancel_invalid_index_and_schema_fail_before_puts(self):
        for responses in (["0"], ["1", "", "project", "", "yes"], ["1", "org", "project", "", "no"]):
            with self.subTest(responses=responses), tempfile.TemporaryDirectory() as directory:
                service = Service("polling")
                answers = iter(responses)
                with self.assertRaises(ValueError):
                    service.helper.setup(service.outputs, None, "polling", Path(directory), run=service.run,
                                         prompt=lambda message: next(answers))
                self.assertEqual(service.puts, [])
                self.assertEqual(service.environment, {})

    def test_deselection_changes_only_owned_sources_preserving_recurrence(self):
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service = Service(mode)
                owned = service.source("OnVstsGitPush")
                foreign = {"id": urlsplit(service.ctx["collection"]).path + "/unrelated", "name": "unrelated", "properties": {"state": "Enabled"}}
                service.resources = {owned["name"]: owned, foreign["name"]: copy.deepcopy(foreign)}
                helper.setup(service.outputs, service.selected(), mode, self.project(directory, mode), run=service.run)
                self.assertEqual(service.resources[foreign["name"]], foreign)
                deselected = service.resources[owned["name"]]["properties"]
                self.assertEqual(deselected["state"], "Disabled")
                self.assertEqual(deselected["recurrence"], {"frequency": "Minute", "interval": 1})
                self.assertEqual(deselected["metadata"]["extra"], "preserve")
                if mode == "webhook":
                    self.assertEqual(service.settings["Unrelated"], "keep")
                    self.assertEqual(service.settings["AzureWebJobs.OnVstsBuildCompleted.Disabled"], "false")
                    self.assertNotIn("callback-secret", json.dumps(service.events))
                    callback = service.puts[0]["properties"]["notificationDetails"]
                    self.assertEqual(callback["authentication"]["value"], "callback-secret")
                previous_puts = len(service.puts)
                helper.setup(service.outputs, service.selected(), mode, Path(directory), run=service.run)
                self.assertEqual(len(service.puts), previous_puts)

    def test_conflicting_deselected_owner_blocks_entire_plan_before_writes(self):
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service = Service(mode)
                conflict = service.source("OnVstsWorkItemUpdated", owned=False)
                service.resources[conflict["name"]] = conflict
                with self.assertRaisesRegex(ValueError, "unowned"):
                    helper.setup(service.outputs, service.selected(), mode, Path(directory), run=service.run)
                self.assertEqual(service.puts, [])
                self.assertEqual(service.settings, {"Unrelated": "keep", "VstsConnection": "old-runtime"})
                self.assertEqual(service.environment, {})

    def test_registration_failure_prevents_enabling_or_exporting_partial_plan(self):
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service = Service(mode)
                service.fail_put = True
                with self.assertRaisesRegex(AssertionError, "Injected"):
                    helper.setup(service.outputs, service.selected(), mode, Path(directory), run=service.run)
                self.assertEqual(service.environment, {})
                if mode == "webhook":
                    self.assertTrue(all(service.settings["AzureWebJobs." + function + ".Disabled"] == "true" for function in helper.OPERATIONS))

    def test_all_nine_sources_register_only_after_consent_in_both_modes(self):
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                service = Service(mode)
                selected = [service.selected(function)[0] for function in helper.OPERATIONS]
                helper.setup(service.outputs, selected, mode, self.project(directory, mode), run=service.run)
                self.assertEqual(len(service.puts), 9)
                self.assertEqual({body["properties"]["operationName"] for body in service.puts}, set(helper.OPERATIONS.values()))
                self.assertTrue(all(body["properties"]["state"] == "Enabled" for body in service.puts))
                if mode == "polling":
                    settings = json.loads(base64.b64decode(service.environment["triggerConfigSettingsEncoded"]))
                    self.assertTrue(all(body["properties"]["deliveryMode"] == "Poll" for body in service.puts))
                    self.assertTrue(all("notificationDetails" not in body["properties"] for body in service.puts))
                else:
                    settings = service.settings
                    self.assertEqual(settings["Unrelated"], "keep")
                    self.assertEqual(settings["VstsConnection"], "https://runtime.logic.azure.com/apim/vsts")
                for function in helper.OPERATIONS:
                    self.assertEqual(settings["AzureWebJobs." + function + ".Disabled"], "false")

    def test_failed_or_wrong_auth_after_consent_never_writes_sources_or_settings(self):
        for mode, helper in HELPERS.items():
            for failure in ("denied", "disconnected", "legacy"):
                with self.subTest(mode=mode, failure=failure), tempfile.TemporaryDirectory() as directory:
                    service = Service(mode)

                    def run(program, arguments, **options):
                        if arguments[:3] == ["connector-namespace", "connection", "authenticate"] and failure == "denied":
                            raise RuntimeError("consent denied")
                        response = service.run(program, arguments, **options)
                        if service.connected and arguments[0] == "rest" and "/connections/" in arguments[arguments.index("--url") + 1]:
                            if failure == "disconnected":
                                response["properties"]["overallStatus"] = "Error"
                            if failure == "legacy":
                                response["properties"]["parameterValueSet"]["name"] = "oauthSetting"
                        return response

                    with self.assertRaises((ValueError, RuntimeError)):
                        helper.setup(service.outputs, service.selected(), mode, Path(directory), run=run)
                    self.assertEqual(service.puts, [])
                    self.assertEqual(service.settings, {"Unrelated": "keep", "VstsConnection": "old-runtime"})
                    self.assertEqual(service.environment, {})

    def test_pending_connection_checks_auth_on_every_read_and_times_out(self):
        for mode, helper in HELPERS.items():
            for failure in ("legacy", "timeout", "failed"):
                with self.subTest(mode=mode, failure=failure):
                    service = Service(mode)
                    reads, waits = [], []

                    def run(program, arguments, **options):
                        reads.append(arguments)
                        return {"properties": {
                            "parameterValueSet": {"name": "oauthSetting" if failure == "legacy" and len(reads) == 2 else "EntraOAuth"},
                            "provisioningState": "Failed" if failure == "failed" else "Creating",
                        }}

                    with self.assertRaises((ValueError, TimeoutError)):
                        helper.authorize(run, service.ctx, service.outputs, wait=waits.append)
                    self.assertEqual(len(reads), 30 if failure == "timeout" else 2 if failure == "legacy" else 1)
                    self.assertEqual(len(waits), len(reads) - 1)

    def test_poll_local_phase_uses_exported_selection_without_reregistering(self):
        helper = HELPERS["polling"]
        service = Service("polling")
        with tempfile.TemporaryDirectory() as directory:
            project = self.project(directory, "polling")
            helper.setup(service.outputs, service.selected(), "polling", project, run=service.run)
            outputs = {**service.outputs, **service.environment}
            with patch.object(helper, "cli", return_value=outputs) as command:
                helper.main(["--mode", "polling", "--project", str(project), "--phase", "local"])
            command.assert_called_once_with("azd", ["env", "get-values", "--output", "json"])
            values = json.loads((project / "local.settings.json").read_text())["Values"]
            self.assertEqual(values["ConnectorNamespace__pollingEndpoint"], service.environment["connectorPollingEndpoint"])
            self.assertEqual(values["AzureWebJobs.OnVstsBuildCompleted.Disabled"], "false")
            self.assertEqual(values["AzureWebJobs.OnVstsGitPush.Disabled"], "true")
            self.assertEqual(values["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
            self.assertNotIn("ConnectorNamespace__credential", values)

    def test_poll_receive_uri_and_provisioning_readiness(self):
        helper = HELPERS["polling"]
        service = Service("polling")
        resource = service.source("OnVstsBuildCompleted")
        name = resource["name"]
        for route, expected in (("/api/triggerconfigs/", "https://example.logic.azure.com"),
                                ("/api/connectorGateways/service/triggerconfigs/", "https://example.logic.azure.com/api/connectorGateways/service")):
            self.assertEqual(helper.poll_endpoint("https://example.logic.azure.com" + route + name + "/receive", name), expected)
        for uri in ("http://example.logic.azure.com/api/triggerconfigs/" + name + "/receive",
                    "https://example.logic.azure.com/api/triggerconfigs/other/receive",
                    "https://user:secret@example.logic.azure.com/api/triggerconfigs/" + name + "/receive",
                    "https://example.logic.azure.com/api/triggerconfigs/" + name + "/receive?code=secret",
                    "https://127.0.0.1/api/triggerconfigs/" + name + "/receive"):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                helper.poll_endpoint(uri, name)
        pending = copy.deepcopy(resource)
        pending["properties"]["provisioningState"] = "Creating"
        waits = []
        result = helper.wait_ready(lambda *args: resource, service.ctx, service.ctx["collection"] + "/" + name,
                                   pending, require_receive=True, wait=waits.append)
        self.assertEqual(result, resource)
        self.assertEqual(waits, [2])
        resource["properties"]["provisioningState"] = "Failed"
        with self.assertRaisesRegex(ValueError, "registration failed"):
            helper.wait_ready(lambda *args: self.fail("No retry after failure"), service.ctx, "unused", resource,
                              require_receive=True, wait=lambda _: self.fail("No wait after failure"))

    def test_full_schema_rejects_unknown_optional_filter_before_any_writes(self):
        for mode, helper in HELPERS.items():
            for name, value in (("unknown", "value"), ("filter", "123")):
                with self.subTest(mode=mode, name=name), tempfile.TemporaryDirectory() as directory:
                    service = Service(mode)
                    selected = service.selected()
                    selected[0]["parameters"].append({"name": name, "value": value})
                    with self.assertRaises(ValueError):
                        helper.setup(service.outputs, selected, mode, Path(directory), run=service.run)
                    self.assertEqual(service.puts, [])
                    self.assertEqual(service.environment, {})

    def test_empty_page_continuation_cycle_and_other_origin(self):
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode):
                service = Service(mode)
                first = service.ctx["collection"] + "?api-version=" + helper.API_VERSION
                second = first + "&page=2"
                pages = iter([{"value": [], "nextLink": second}, {"value": [{"name": "later", "id": "later"}]}])
                result = helper.list_triggers(lambda *args: next(pages), service.ctx)
                self.assertEqual(result, [{"name": "later", "id": "later"}])
                for next_link in (first, second.replace("management.azure.com", "attacker.example")):
                    with self.assertRaises(ValueError):
                        helper.list_triggers(lambda *args: {"value": [], "nextLink": next_link}, service.ctx)

    def test_local_settings_preserve_merge_isolation_and_atomic_failure(self):
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                project = self.project(directory, mode)
                helper.write_local(project, {"new": "value"}, force=False)
                path = project / "local.settings.json"
                before = path.read_bytes()
                self.assertEqual(json.loads(before)["Values"]["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
                helper.write_local(project, {"new": "changed"}, force=False)
                self.assertEqual(path.read_bytes(), before)
                with patch.object(helper.os, "replace", side_effect=OSError("injected")):
                    with self.assertRaises(OSError):
                        helper.write_local(project, {"new": "changed"}, force=True)
                self.assertEqual(path.read_bytes(), before)
                helper.write_local(project, {"another": "value", "ConnectorNamespace__credential": "managedidentity"}, force=True)
                values = json.loads(path.read_text())["Values"]
                self.assertEqual(values["new"], "value")
                self.assertEqual(values["another"], "value")
                self.assertNotIn("ConnectorNamespace__credential", values)
                self.assertEqual(list(project.glob(".vsts-settings-*")), [])

    def test_private_request_cleanup_on_failure(self):
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode):
                path = None

                def failing_request():
                    nonlocal path
                    with helper.private_json({"secret": "value"}) as argument:
                        path = Path(argument[1:])
                        self.assertEqual(json.loads(path.read_text()), {"secret": "value"})
                        raise RuntimeError("injected")

                self.assertRaisesRegex(RuntimeError, "injected", failing_request)
                self.assertIsNotNone(path)
                self.assertFalse(path.exists())
                self.assertFalse(path.parent.exists())

    @unittest.skipUnless(os.name == "nt", "Windows DACL check")
    def test_windows_acl_contains_only_current_user_and_is_protected(self):
        command = """
        $ErrorActionPreference = 'Stop'
        $acl = Get-Acl -LiteralPath $env:VSTS_ACL_TEST_PATH
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $rules = @($acl.Access | ForEach-Object {
            @{ Sid=$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value; Inherited=$_.IsInherited }
        })
        @{ Protected=$acl.AreAccessRulesProtected; Current=$sid; Rules=$rules } | ConvertTo-Json -Depth 4 -Compress
        """
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                for path in (Path(directory).resolve(), Path(directory).resolve() / "settings.json"):
                    if path.suffix:
                        path.write_text("{}")
                    helper.protect_path(path)
                    result = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", command],
                                            capture_output=True, text=True, check=True,
                                            env={**os.environ, "VSTS_ACL_TEST_PATH": str(path)})
                    acl = json.loads(result.stdout)
                    self.assertTrue(acl["Protected"])
                    self.assertEqual(acl["Rules"], [{"Sid": acl["Current"], "Inherited": False}])

    def test_detect_existing_app_and_fail_closed_on_inventory_error(self):
        for mode, helper in HELPERS.items():
            with self.subTest(mode=mode):
                service = Service(mode)
                calls = []

                def run(program, arguments):
                    calls.append((program, arguments))
                    if program == "azd":
                        return None
                    return True if arguments[0] == "group" else [{"name": "func-review"}]

                helper.detect_app(service.outputs, run=run)
                self.assertEqual(calls[-1], ("azd", ["env", "set", "VSTS_FUNCTION_APP_EXISTS", "true"]))
                calls.clear()

                def denied(program, arguments):
                    calls.append((program, arguments))
                    raise RuntimeError("denied")

                with self.assertRaises(RuntimeError):
                    helper.detect_app(service.outputs, run=denied)
                self.assertFalse(any(program == "azd" for program, _ in calls))


class BindingTests(unittest.TestCase):
    """Exercise SDK indexing and actual converter dispatch, not synthetic annotations."""

    def test_all_eighteen_handlers_index_convert_nested_fields_and_log_counts(self):
        import azure.functions as functions
        import azurefunctions.extensions.connectors.visualstudioteamservices as devops
        from azurefunctions.extensions.base import Datum

        self.assertTrue(hasattr(functions, "DeliveryMode"))
        records = {"id": 7, "pushId": 8, "pullRequestId": 9, "changesetId": 10,
                   "project": {"id": "project-id", "name": "review-project"},
                   "definition": {"id": 1, "name": "review-build"},
                   "fields": {"System.Title": "private-title", "Custom.Flag": False}}
        for mode in HELPERS:
            module = load(mode, ROOT / mode / "function_app.py")
            handlers = module.app.get_functions()
            self.assertEqual(len(handlers), 9)
            for function in handlers:
                with self.subTest(mode=mode, function=function.get_function_name()):
                    handler = function.get_user_function()
                    annotation = handler.__annotations__["event"]
                    item_type = get_args(annotation)[0]
                    self.assertEqual(annotation, List[item_type])
                    self.assertTrue(devops.ConnectorConverter.check_input_type_annotation(annotation))
                    trigger = json.loads(function.get_function_json())["bindings"][0]
                    self.assertEqual(trigger["direction"].lower(), "in")
                    self.assertEqual(trigger["type"], "connectorTrigger")
                    self.assertEqual(trigger["name"], "event")
                    self.assertEqual(trigger["connection"], "ConnectorNamespace" if mode == "polling" else "VstsConnection")
                    if mode == "polling":
                        self.assertEqual(trigger["deliveryMode"].lower(), "poll")
                        self.assertEqual(trigger["triggerConfigName"], "%" + function.get_function_name() + "TriggerConfigName%")
                    for payload, count in (({"body": records}, 1), ({"body": {"value": [records]}}, 1),
                                           ({"body": {"value": []}}, 0), ([records, records], 2),
                                           ({"body": records, "headers": {}, "statusCode": 200}, 1)):
                        items = devops.ConnectorConverter.decode(Datum(type="json", value=payload), trigger_metadata={}, pytype=annotation)
                        self.assertEqual(len(items), count)
                        if count:
                            self.assertEqual(type(items[0]).__name__, item_type.__name__)
                            if item_type is devops.BuildResult:
                                self.assertEqual(items[0].definition.name, "review-build")
                            if item_type is devops.TriggerWorkItemResponse:
                                self.assertEqual(items[0].fields["Custom.Flag"], False)
                        with patch.object(module.logging, "info") as log:
                            self.assertIsNone(handler(items))
                        log.assert_called_once_with("Received " + function.get_function_name() + " trigger with %d items.", count)
                    with self.assertRaises(ValueError):
                        devops.ConnectorConverter.decode(Datum(type="string", value="not-json"), trigger_metadata={}, pytype=annotation)
                    for payload in ([None], ["not-a-record"], [1]):
                        with self.assertRaises((ValueError, TypeError)):
                            devops.ConnectorConverter.decode(Datum(type="json", value=payload), trigger_metadata={}, pytype=annotation)


class CopyAndConfigurationTests(unittest.TestCase):
    """Check copy boundaries, dependency markers, hooks and merge expressions."""

    def test_posix_hooks_forward_copy_local_paths_and_fail_closed(self):
        shell = (str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
                 if os.name == "nt" else shutil.which("sh"))
        if not shell or not Path(shell).is_file():
            self.skipTest("Install a POSIX shell (Git Bash on Windows) to exercise shell hooks.")
        command = """
        set -eu
        stub_dir=$VSTS_REVIEW_BIN
        hook=$VSTS_REVIEW_HOOK
        if command -v cygpath >/dev/null 2>&1; then
            stub_dir=$(cygpath -u "$stub_dir")
            hook=$(cygpath -u "$hook")
        fi
        PATH="$stub_dir:$PATH"
        export PATH
        test "$(command -v python3)" = "$stub_dir/python3"
        set --
        if [ "$VSTS_REVIEW_FORCE" = true ]; then set -- --force-local-settings; fi
        exec sh "$hook" "$@"
        """

        def native_path(value):
            if os.name == "nt" and len(value) > 2 and value[0] == "/" and value[2] == "/":
                value = value[1] + ":" + value[2:]
            return Path(value).resolve()

        for mode in HELPERS:
            names = ("preprovision", "postdeploy", "prepare-app") if mode == "polling" else ("preprovision", "postdeploy")
            with tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory).resolve()
                project, binaries = temporary / "copied mode", temporary / "stub bin"
                shutil.copytree(ROOT / mode, project, ignore=shutil.ignore_patterns("__pycache__", ".azure", ".venv", "local.settings.json"))
                binaries.mkdir()
                stub = binaries / "python3"
                stub.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@"\nexit "$VSTS_REVIEW_EXIT_CODE"\n', encoding="utf-8")
                stub.chmod(0o700)
                for name in names:
                    with self.subTest(mode=mode, hook=name):
                        env = {**os.environ, "VSTS_REVIEW_HOOK": str(project / "infra/scripts" / (name + ".sh")),
                               "VSTS_REVIEW_BIN": str(binaries), "VSTS_REVIEW_EXIT_CODE": "0",
                               "VSTS_REVIEW_FORCE": str(name == "postdeploy").lower()}
                        result = subprocess.run([shell, "-c", command], env=env, cwd=directory,
                                                capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        arguments = result.stdout.splitlines()
                        self.assertEqual(native_path(arguments[0]), project / "infra/scripts/setup.py")
                        self.assertEqual(arguments[arguments.index("--mode") + 1], mode)
                        self.assertEqual(native_path(arguments[arguments.index("--project") + 1]), project)
                        if name == "postdeploy":
                            self.assertIn("--force-local-settings", arguments)
                        env["VSTS_REVIEW_EXIT_CODE"] = "7"
                        result = subprocess.run([shell, "-c", command], env=env, cwd=directory,
                                                capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 7, result.stderr)

    @unittest.skipUnless(os.name == "nt" and shutil.which("pwsh"), "Windows PowerShell hook check")
    def test_powershell_hooks_forward_copy_local_paths_and_fail_closed(self):
        command = """
        function global:python {
            ConvertTo-Json -InputObject @($args) -Compress
            $global:LASTEXITCODE = [int]$env:VSTS_REVIEW_EXIT_CODE
        }
        if ($env:VSTS_REVIEW_FORCE -eq 'true') { & $env:VSTS_REVIEW_HOOK -ForceLocalSettings }
        else { & $env:VSTS_REVIEW_HOOK }
        """
        for mode in HELPERS:
            names = ("preprovision", "postdeploy", "prepare-app") if mode == "polling" else ("preprovision", "postdeploy")
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory).resolve() / "copied mode"
                shutil.copytree(ROOT / mode, project, ignore=shutil.ignore_patterns("__pycache__", ".azure", ".venv", "local.settings.json"))
                for name in names:
                    with self.subTest(mode=mode, hook=name):
                        env = {**os.environ, "VSTS_REVIEW_HOOK": str(project / "infra/scripts" / (name + ".ps1")),
                               "VSTS_REVIEW_FORCE": str(name == "postdeploy").lower(), "VSTS_REVIEW_EXIT_CODE": "0"}
                        result = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", command],
                                                env=env, cwd=directory, capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        arguments = json.loads(result.stdout)
                        self.assertEqual(Path(arguments[0]), project / "infra/scripts/setup.py")
                        self.assertEqual(arguments[arguments.index("--mode") + 1], mode)
                        self.assertEqual(Path(arguments[arguments.index("--project") + 1]), project)
                        if name == "postdeploy":
                            self.assertIn("--force-local-settings", arguments)
                        if name == "prepare-app" or mode == "webhook" and name == "preprovision":
                            self.assertEqual(arguments[arguments.index("--phase") + 1], "prepare-app")
                        if mode == "polling" and name == "postdeploy":
                            self.assertEqual(arguments[arguments.index("--phase") + 1], "local")
                        env["VSTS_REVIEW_EXIT_CODE"] = "7"
                        result = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", command],
                                                env=env, cwd=directory, capture_output=True, text=True, timeout=30)
                        self.assertNotEqual(result.returncode, 0)

    def test_modes_work_without_parent_files(self):
        for mode in HELPERS:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                project = Path(directory).resolve() / mode
                shutil.copytree(ROOT / mode, project, ignore=shutil.ignore_patterns(".azure", ".venv", "__pycache__", "local.settings.json"))
                result = subprocess.run([os.sys.executable, str(project / "infra/scripts/setup.py"), "--help"], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                for path in project.rglob("*"):
                    if path.is_file() and path.suffix in {".ps1", ".sh", ".md"}:
                        self.assertNotIn("../../../scripts", path.read_text())
                        if path.suffix == ".md":
                            self.assertNotIn("](../", path.read_text())

    def test_platform_hooks_define_their_own_execution_controls(self):
        import yaml

        for mode in HELPERS:
            config = yaml.safe_load((ROOT / mode / "azure.yaml").read_text())
            hooks = list(config["hooks"].values())
            for layer in config.get("infra", {}).get("layers", []):
                hooks.extend(layer.get("hooks", {}).values())
            for hook in hooks:
                with self.subTest(mode=mode, hook=hook):
                    self.assertEqual(set(hook), {"windows", "posix"})
                    for platform in ("windows", "posix"):
                        self.assertIs(hook[platform]["continueOnError"], False)
                        self.assertIn("run", hook[platform])

    def test_runtime_contracts_and_layer_order(self):
        import yaml
        from packaging.requirements import Requirement

        for mode in HELPERS:
            project = ROOT / mode
            requirements = [Requirement(line) for line in (project / "requirements.txt").read_text().splitlines()]
            self.assertNotIn("azure-connectors", [item.name for item in requirements])
            for version, minimum in (("3.12", "1.27.0b1"), ("3.13", "2.4.0"), ("3.14", "2.4.0")):
                matches = [item for item in requirements if item.name == "azure-functions" and item.marker.evaluate({"python_version": version})]
                self.assertEqual(len(matches), 1)
                self.assertEqual(str(matches[0].specifier), ">=" + minimum)
            host = json.loads((project / "host.json").read_text())
            self.assertEqual(host["extensionBundle"], {"id": "Microsoft.Azure.Functions.ExtensionBundle", "version": "[4.41.2, 5.0.0)"})
            settings = json.loads((project / "local.settings.example.json").read_text())["Values"]
            self.assertEqual(settings["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
            self.assertNotIn("namespace-msi", (project / "infra/namespace.bicep").read_text())
            self.assertIn("developerAccess", (project / "infra/namespace.bicep").read_text())
            self.assertIn("functionAccess", (project / "infra/function-access.bicep").read_text())
        config = yaml.safe_load((ROOT / "polling/azure.yaml").read_text())
        self.assertEqual([layer["name"] for layer in config["infra"]["layers"]], ["foundation", "triggers", "app"])
        steps = [step["azd"] for step in config["workflows"]["up"]]
        self.assertEqual(steps, ["package --all", "provision foundation", "provision triggers", "provision app", "deploy --all"])
        trigger_hook = config["infra"]["layers"][1]["hooks"]["preprovision"]
        self.assertTrue(trigger_hook["windows"]["interactive"])
        self.assertTrue(trigger_hook["posix"]["interactive"])
        self.assertNotIn("Microsoft.Web/sites@", (ROOT / "polling/infra/resources.bicep").read_text())
        self.assertIn("union(existingAppSettings", (ROOT / "polling/infra/app-settings.bicep").read_text())
        self.assertIn("existingAppSettings, {", (ROOT / "webhook/infra/resources.bicep").read_text())


class BicepTests(unittest.TestCase):
    """Compile real templates and evaluate settings merges with offline snapshots."""

    @classmethod
    def setUpClass(cls):
        candidate = os.environ.get("BICEP_CLI") or shutil.which("bicep") or str(Path.home() / ".azure/bin/bicep.exe")
        if not Path(candidate).is_file():
            raise unittest.SkipTest("Install the standalone Bicep CLI or set BICEP_CLI for offline template checks.")
        cls.compiler = candidate
        cls.templates = {}
        for path in sorted(ROOT.rglob("*.bicep")):
            result = subprocess.run([cls.compiler, "build", str(path), "--stdout", "--no-restore"],
                                    capture_output=True, text=True, encoding="utf-8", timeout=60)
            if result.returncode:
                raise AssertionError(str(path) + "\n" + result.stderr)
            cls.templates[path.relative_to(ROOT).as_posix()] = json.loads(result.stdout)

    def test_every_bicep_file_compiles_and_foundation_has_no_app_or_sources(self):
        self.assertEqual(len(self.templates), 12)
        foundation = self.templates["polling/infra/resources.bicep"]
        types = {resource["type"].lower() for resource in foundation["resources"]}
        self.assertNotIn("microsoft.web/sites", types)
        self.assertFalse(any("triggerconfigs" in resource_type for resource_type in types))
        for mode in HELPERS:
            template = self.templates[mode + "/infra/namespace.bicep"]
            policies = [resource for resource in template["resources"] if resource["type"].endswith("/accessPolicies")]
            self.assertEqual(len(policies), 1)
            self.assertEqual(policies[0]["properties"]["principal"]["identity"]["objectId"], "[parameters('userPrincipalId')]")
            access = self.templates[mode + "/infra/function-access.bicep"]
            policies = [resource for resource in access["resources"] if resource["type"].endswith("/accessPolicies")]
            self.assertEqual(len(policies), 1)
            self.assertEqual(policies[0]["properties"]["principal"]["identity"]["objectId"], "[parameters('functionPrincipalId')]")

    def test_parameter_files_supply_exact_entrypoint_contracts(self):
        for path in ROOT.rglob("*.parameters.json"):
            with self.subTest(path=path):
                template = self.templates[path.relative_to(ROOT).as_posix().replace(".parameters.json", ".bicep")]
                supplied = json.loads(path.read_text(encoding="utf-8"))["parameters"]
                expected = template["parameters"]
                self.assertFalse(set(supplied) - set(expected))
                self.assertFalse({name for name, value in expected.items() if "defaultValue" not in value} - set(supplied))

    def test_reprovision_snapshots_preserve_unrelated_values_and_listener_selection(self):
        for mode in HELPERS:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                temporary = Path(directory).resolve()
                infra = temporary / "infra"
                shutil.copytree(ROOT / mode / "infra", infra)
                settings = {"Unrelated": "keep", "PYTHON_ISOLATE_WORKER_DEPENDENCIES": "0",
                            "AzureWebJobs.OnVstsBuildCompleted.Disabled": "false",
                            "AzureWebJobs.OnVstsGitPush.Disabled": "true"}
                (infra / "existing.json").write_text(json.dumps(settings), encoding="utf-8")
                parameters = {
                    "storageName": "streview", "insightsName": "appi-review",
                }
                if mode == "polling":
                    target = "app-settings.bicep"
                    listeners = {"AzureWebJobs." + function + ".Disabled": "true" for function in HELPERS[mode].OPERATIONS}
                    listeners.update({function + "TriggerConfigName": "config-" + function for function in HELPERS[mode].OPERATIONS})
                    listeners["AzureWebJobs.OnVstsBuildCompleted.Disabled"] = "false"
                    parameters.update(functionAppName="func-review", connectorPollingEndpoint="https://example.logic.azure.com",
                                      triggerConfigSettingsEncoded=base64.b64encode(json.dumps(listeners).encode()).decode())
                else:
                    target = "resources.bicep"
                    parameters = {"environmentName": "review", "location": "eastus",
                                  "connectorNamespaceLocation": "brazilsouth", "userPrincipalId": "11111111-1111-1111-1111-111111111111"}
                # NOTE: Snapshot evaluation hides secure parameters and cannot read live resources.
                # Replace only those boundaries in the temporary copy, leaving the merge unchanged.
                boundary_values = {
                    "@secure()\nparam existingAppSettings object": "var existingAppSettings = loadJsonContent('./existing.json')",
                    "insights.properties.ConnectionString": "'instrumentation-placeholder'",
                }
                if mode == "webhook":
                    boundary_values["namespace.outputs.connectionRuntimeUrl"] = "'https://runtime.logic.azure.com/apim/vsts'"
                template_path = infra / target
                template = template_path.read_text(encoding="utf-8")
                for boundary, value in boundary_values.items():
                    self.assertEqual(template.count(boundary), 1)
                    template = template.replace(boundary, value)
                template_path.write_text(template, encoding="utf-8")
                source = "using './" + target + "'\n"
                source += "".join("param " + name + " = '" + value + "'\n" for name, value in parameters.items())
                parameter_file = infra / "review.bicepparam"
                parameter_file.write_text(source, encoding="utf-8")
                before = set(infra.glob("*.json"))
                result = subprocess.run([self.compiler, "snapshot", str(parameter_file), "--mode", "overwrite",
                                         "--subscription-id", "00000000-0000-0000-0000-000000000001", "--resource-group", "rg-review",
                                         "--location", "eastus"], capture_output=True, text=True, encoding="utf-8", timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                snapshots = set(infra.glob("*.json")) - before
                self.assertEqual(len(snapshots), 1, result.stdout + result.stderr)
                snapshot = json.loads(snapshots.pop().read_text(encoding="utf-8"))
                resources = snapshot["predictedResources"]
                settings_resources = [resource for resource in resources if resource["type"].lower() == "microsoft.web/sites/config"]
                self.assertEqual(len(settings_resources), 1, snapshot)
                values = settings_resources[0]["properties"]
                self.assertEqual(values["Unrelated"], "keep")
                self.assertEqual(values["AzureWebJobs.OnVstsBuildCompleted.Disabled"], "false")
                self.assertEqual(values["AzureWebJobs.OnVstsGitPush.Disabled"], "true")
                self.assertEqual(values["AzureWebJobs.OnVstsWorkItemUpdated.Disabled"], "true")
                self.assertEqual(values["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
                if mode == "polling":
                    self.assertEqual(values["ConnectorNamespace__pollingEndpoint"], parameters["connectorPollingEndpoint"])
                    self.assertEqual(values["OnVstsBuildCompletedTriggerConfigName"], "config-OnVstsBuildCompleted")


if __name__ == "__main__":
    unittest.main()