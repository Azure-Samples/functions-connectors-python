# Copyright (c) Microsoft Corporation.  All rights reserved.
# Licensed under the MIT License.

"""Offline Planner regression tests. No test makes an Azure request."""

import base64
import copy
import importlib.util
import io
import json
import os
import shutil
import tempfile
import typing
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MODES = ("polling", "webhook")
FUNCTIONS = ("OnPlannerCompleteTask", "OnPlannerNewTask", "OnPlannerTaskAssignedToMe")


def load(mode, relative="infra/scripts/setup.py", root=ROOT):
    """Load exactly the helper or app under test, never a sibling implementation."""
    spec = importlib.util.spec_from_file_location("planner_" + mode + relative.replace("/", "_"), root / mode / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selection(module, functions=FUNCTIONS):
    """Use synthetic real-shaped identifiers, not rejected example placeholders."""
    return [{"functionName": name, "operationName": module.OPERATIONS[name][0],
             "parameters": [{"name": key, "value": "synthetic-" + key}
                            for key in module.OPERATIONS[name][1]]} for name in functions]


class AzureDouble:
    """Emulate ARM and settings calls, rejecting unexpected or unpinned commands."""

    def __init__(self, mode, *, exists=False, consent=True):
        self.mode, self.exists, self.connected = mode, exists, consent
        self.complete_consent = True
        self.outputs = {"AZURE_SUBSCRIPTION_ID": "synthetic-subscription", "AZURE_ENV_NAME": "planner-test",
                        "resourceGroupName": "rg-planner-test", "functionAppName": "func-planner-test",
                        "connectorNamespaceName": "cn-planner-test", "connectorNamespaceConnectionName": "planner-test"}
        if mode == "webhook":
            self.outputs["functionAppDefaultHostname"] = "func-planner-test.azurewebsites.net"
        self.resources, self.calls, self.writes, self.temporary_paths = {}, [], [], []
        self.settings = {"CUSTOM_SETTING": "preserve-me"}
        self.status, self.gateway = "Succeeded", "https://synthetic-gateway.azure.com/connectors/planner"
        self.empty_first_page = False
        self.bad_next = None
        self.fail_final_settings = False

    def __call__(self, program, *arguments, interactive=False):
        self.calls.append((program, arguments, interactive))
        if program == "azd":
            if arguments[:2] == ("env", "get-values"):
                return copy.deepcopy(self.outputs)
            if arguments[:2] == ("env", "set"):
                self.outputs[arguments[2]] = arguments[3]
                return None
            raise AssertionError(arguments)
        if program != "az" or "--subscription" not in arguments:
            raise AssertionError("Unexpected or unpinned command.")
        if arguments[arguments.index("--subscription") + 1] != self.outputs["AZURE_SUBSCRIPTION_ID"]:
            raise AssertionError("Wrong subscription.")
        if arguments[:2] == ("functionapp", "list"):
            return ([{"name": self.outputs["functionAppName"], "resourceGroup": self.outputs["resourceGroupName"],
                      "tags": {"azd-env-name": self.outputs["AZURE_ENV_NAME"], "azd-service-name": "function-app"}}]
                    if self.exists else [])
        if arguments[:2] == ("connector-namespace", "connection"):
            if arguments[2] == "authenticate":
                if not interactive or "--no-access-policy" not in arguments:
                    raise AssertionError("OAuth must remain interactive without implicit policies.")
                self.connected = self.complete_consent
                return None
            if arguments[2] == "show":
                return {"properties": {"overallStatus": "Connected" if self.connected else "Error"}}
        if arguments[:3] == ("functionapp", "keys", "list"):
            return {"systemKeys": {"connector_extension": "synthetic-secret"}, "functionKeys": {"default": "wrong-key"}}
        if arguments[:3] == ("functionapp", "config", "appsettings"):
            if not self.connected:
                raise AssertionError("Settings changed before consent.")
            if arguments[3] == "set":
                path = Path(arguments[arguments.index("--settings") + 1][1:])
                self.temporary_paths.append(path)
                values = json.loads(path.read_text(encoding="utf-8"))
                self.writes.append(("settings", values))
                if self.fail_final_settings and "false" in values.values():
                    raise RuntimeError("Synthetic settings failure.")
                self.settings.update(values)
                return None
            return [{"name": name, "value": value} for name, value in self.settings.items()]
        if arguments[0] == "rest":
            method, url = arguments[arguments.index("--method") + 1], arguments[arguments.index("--url") + 1]
            parsed = urlsplit(url)
            if parsed.path.casefold().endswith("/triggerconfigs"):
                if self.bad_next:
                    return {"value": [], "nextLink": self.bad_next}
                if self.empty_first_page and "page=2" not in parsed.query:
                    return {"value": [], "nextLink": url + "&page=2"}
                return {"value": copy.deepcopy(list(self.resources.values()))}
            name = unquote(parsed.path.rsplit("/", 1)[1])
            if method == "put":
                if not self.connected:
                    raise AssertionError("Source created before consent.")
                path = Path(arguments[arguments.index("--body") + 1][1:])
                self.temporary_paths.append(path)
                properties = json.loads(path.read_text(encoding="utf-8"))["properties"]
                if any(key in properties for key in ("provisioningState", "pollingEndpoints")):
                    raise AssertionError("Read-only fields leaked to PUT.")
                self.writes.append((name, copy.deepcopy(properties)))
                properties["provisioningState"] = self.status
                if self.mode == "polling":
                    properties["pollingEndpoints"] = {"receiveUri": self.gateway + "/api/triggerconfigs/" + name + "/receive"}
                self.resources[name] = {"name": name, "id": parsed.path, "properties": properties}
            return copy.deepcopy(self.resources[name])
        raise AssertionError(arguments)


class SetupTests(unittest.TestCase):
    """Exercise both shipped helpers, including the actual phase entry points."""

    def test_import_has_no_cli_calls(self):
        with patch("subprocess.run", side_effect=AssertionError("Import must not call Azure.")):
            for mode in MODES:
                load(mode)

    def test_invalid_selections_fail_before_writes(self):
        for mode in MODES:
            module, azure = load(mode), AzureDouble(mode)
            valid = selection(module)
            wrong_keys = copy.deepcopy(valid)
            wrong_keys[0]["parameters"][0]["name"] = "planId"
            placeholders = copy.deepcopy(valid)
            placeholders[0]["parameters"][0]["value"] = "<group-id>"
            for invalid in ([], valid + valid, wrong_keys, placeholders, [{"functionName": "unknown"}]):
                with self.subTest(mode=mode, invalid=invalid):
                    with self.assertRaises(ValueError):
                        module.Setup(azure.outputs, mode, run=azure).configure(invalid)
                    self.assertEqual(azure.calls, [])

    def test_consent_failure_never_writes_sources_or_settings(self):
        for mode in MODES:
            module, azure = load(mode), AzureDouble(mode, consent=False)
            azure.complete_consent = False
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "Connected"):
                module.Setup(azure.outputs, mode, run=azure).configure(selection(module))
            self.assertEqual(azure.writes, [])

    def test_all_events_rerun_and_deselection_preserve_writable_properties(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                module, azure = load(mode), AzureDouble(mode)
                setup = module.Setup(azure.outputs, mode, run=azure)
                arguments = {"sources_only": True, "app_exists": False} if mode == "polling" else {}
                values = setup.configure(selection(module), **arguments)
                self.assertEqual(len(azure.resources), 3)
                self.assertTrue(all(values[f"AzureWebJobs.{name}.Disabled"] == "false" for name in FUNCTIONS))
                for resource in azure.resources.values():
                    self.assertEqual(resource["properties"]["state"], "Enabled")
                    if mode == "webhook":
                        details = resource["properties"]["notificationDetails"]
                        self.assertEqual(details["authentication"], {"type": "QueryString", "name": "code", "value": "synthetic-secret"})
                        self.assertNotIn("code=", details["callbackUrl"])
                        self.assertTrue(details["callbackUrl"].startswith("https://" + azure.outputs["functionAppDefaultHostname"]))
                azure.writes.clear()
                setup.configure(selection(module), **arguments)
                self.assertFalse(any(name != "settings" for name, _ in azure.writes))
                deselected = azure.resources[setup.name(FUNCTIONS[0])]["properties"]
                deselected.update(recurrence={"frequency": "Minute", "interval": 7}, custom={"integer": 2**60})
                deselected["metadata"]["custom"] = "preserve"
                before = copy.deepcopy(deselected)
                values = setup.configure(selection(module, FUNCTIONS[2:]), **arguments)
                after = azure.resources[setup.name(FUNCTIONS[0])]["properties"]
                before["state"] = "Disabled"
                self.assertEqual(before, after)
                self.assertEqual(values[f"AzureWebJobs.{FUNCTIONS[0]}.Disabled"], "true")
                self.assertEqual(values[f"AzureWebJobs.{FUNCTIONS[2]}.Disabled"], "false")
                self.assertEqual(azure.settings["CUSTOM_SETTING"], "preserve-me")
                self.assertTrue(all(not path.exists() for path in azure.temporary_paths))

    def test_foreign_deselected_source_blocks_every_write(self):
        for mode in MODES:
            module, azure = load(mode), AzureDouble(mode)
            setup = module.Setup(azure.outputs, mode, run=azure)
            arguments = {"sources_only": True, "app_exists": False} if mode == "polling" else {}
            setup.configure(selection(module), **arguments)
            azure.resources[setup.name(FUNCTIONS[0])]["properties"]["metadata"]["functionAppName"] = "foreign-app"
            azure.writes.clear()
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "ownership"):
                setup.configure(selection(module, FUNCTIONS[2:]), **arguments)
            self.assertEqual(azure.writes, [])

    def test_failed_registration_leaves_existing_listeners_disabled(self):
        for mode in MODES:
            module, azure = load(mode), AzureDouble(mode, exists=True)
            azure.status = "Failed"
            arguments = {"sources_only": True, "app_exists": True} if mode == "polling" else {}
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "registration failed"):
                module.Setup(azure.outputs, mode, run=azure).configure(selection(module), **arguments)
            self.assertTrue(all(azure.settings[f"AzureWebJobs.{name}.Disabled"] == "true" for name in FUNCTIONS))

    def test_webhook_settings_failure_rolls_back_and_never_logs_key(self):
        module, azure = load("webhook"), AzureDouble("webhook")
        azure.fail_final_settings = True
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaisesRegex(RuntimeError, "settings failure"):
            module.Setup(azure.outputs, run=azure).configure(selection(module))
        self.assertNotIn("synthetic-secret", output.getvalue())
        self.assertTrue(all(azure.settings[f"AzureWebJobs.{name}.Disabled"] == "true" for name in FUNCTIONS))

    def test_pagination_empty_page_and_foreign_continuation(self):
        for mode in MODES:
            module, azure = load(mode), AzureDouble(mode)
            setup = module.Setup(azure.outputs, mode, run=azure)
            azure.empty_first_page = True
            azure.resources["sentinel"] = {"name": "sentinel"}
            self.assertEqual(setup.list_triggers(), [{"name": "sentinel"}])
            azure.bad_next = "https://other.invalid/triggerConfigs?page=2"
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "continuation"):
                setup.list_triggers()

    def test_polling_sources_phase_has_no_app_or_callback_dependency(self):
        module, azure = load("polling"), AzureDouble("polling")
        with patch.object(module, "cli", azure), patch.dict(os.environ, {"PLANNER_TRIGGER_INPUTS": json.dumps(selection(module))}):
            module.main(["--mode", "polling", "--phase", "sources", "--project", str(ROOT / "polling")])
        self.assertEqual(azure.outputs["PLANNER_POLLING_ENDPOINT"], azure.gateway)
        values = json.loads(base64.b64decode(azure.outputs["PLANNER_LISTENER_SETTINGS_ENCODED"]))
        self.assertEqual(values["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
        self.assertTrue(all(values[f"AzureWebJobs.{name}.Disabled"] == "false" for name in FUNCTIONS))
        self.assertFalse(any(arguments[:2] in (("functionapp", "config"), ("functionapp", "keys"))
                             for program, arguments, _ in azure.calls if program == "az"))

    def test_existing_polling_app_stays_disabled_until_the_app_layer(self):
        module, azure = load("polling"), AzureDouble("polling", exists=True, consent=False)
        values = module.Setup(azure.outputs, "polling", run=azure).configure(
            selection(module, FUNCTIONS[2:]), sources_only=True, app_exists=True)
        self.assertTrue(azure.connected)
        self.assertTrue(all(azure.settings[f"AzureWebJobs.{name}.Disabled"] == "true" for name in FUNCTIONS))
        self.assertEqual(values[f"AzureWebJobs.{FUNCTIONS[2]}.Disabled"], "false")
        self.assertEqual(len(azure.resources), 1)
        self.assertEqual(azure.settings["CUSTOM_SETTING"], "preserve-me")

    def test_every_ownership_field_blocks_writes(self):
        for mode in MODES:
            module, azure = load(mode), AzureDouble(mode)
            setup = module.Setup(azure.outputs, mode, run=azure)
            arguments = {"sources_only": True, "app_exists": False} if mode == "polling" else {}
            setup.configure(selection(module, FUNCTIONS[2:]), **arguments)
            original = copy.deepcopy(azure.resources)
            for field in ("id", "name", "operationName", "deliveryMode", "connectionName", "connectorName"):
                azure.resources = copy.deepcopy(original)
                resource = azure.resources[setup.name(FUNCTIONS[2])]
                target = (resource if field in {"id", "name"} else resource["properties"]["connectionDetails"]
                          if field in {"connectionName", "connectorName"} else resource["properties"])
                target[field] = "foreign"
                azure.writes.clear()
                with self.subTest(mode=mode, field=field), self.assertRaisesRegex(ValueError, "ownership"):
                    setup.configure(selection(module, FUNCTIONS[2:]), **arguments)
                self.assertEqual(azure.writes, [])

    def test_explicit_input_file_survives_layer_hook_reruns(self):
        module, azure = load("polling"), AzureDouble("polling")
        with tempfile.TemporaryDirectory() as directory:
            inputs = Path(directory) / "chosen.json"
            inputs.write_text(json.dumps(selection(module, FUNCTIONS[2:])), encoding="utf-8")
            with patch.object(module, "cli", azure), patch.dict(os.environ, {"PLANNER_INPUTS_FILE": str(inputs), "PLANNER_TRIGGER_INPUTS": "invalid"}):
                for _ in range(2):
                    module.main(["--mode", "polling", "--phase", "sources", "--project", str(ROOT / "polling")])
            self.assertEqual(len(azure.resources), 1)
            self.assertEqual(next(iter(azure.resources.values()))["properties"]["operationName"], "OnTaskAssignedToMe_V2")

    def test_polling_gateway_mismatch_keeps_existing_listeners_disabled(self):
        module, azure = load("polling"), AzureDouble("polling", exists=True)
        setup = module.Setup(azure.outputs, "polling", run=azure)
        resolve = module.polling_endpoint
        calls = []

        def different_gateway(uri, name):
            calls.append(name)
            return resolve(uri, name) + ("/other" if len(calls) > 1 else "")

        with patch.object(module, "polling_endpoint", different_gateway), self.assertRaisesRegex(ValueError, "inconsistent"):
            setup.configure(selection(module), sources_only=True, app_exists=True)
        self.assertTrue(all(azure.settings[f"AzureWebJobs.{name}.Disabled"] == "true" for name in FUNCTIONS))

    def test_polling_local_phase_only_writes_local_settings(self):
        module, azure = load("polling"), AzureDouble("polling")
        azure.outputs.update(connectorPollingEndpoint=azure.gateway,
                             triggerConfigSettingsEncoded=base64.b64encode(json.dumps({
                                 **{name + "TriggerConfigName": "config-" + name for name in FUNCTIONS},
                                 **{f"AzureWebJobs.{name}.Disabled": "false" for name in FUNCTIONS},
                             }).encode()).decode())
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "cli", azure):
            module.main(["--mode", "polling", "--phase", "local", "--project", directory])
            values = json.loads((Path(directory) / "local.settings.json").read_text())["Values"]
            self.assertEqual(values["ConnectorNamespace__pollingEndpoint"], azure.gateway)
            self.assertEqual(values["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
            self.assertNotIn("ConnectorNamespace__credential", values)
            self.assertFalse(any(program == "az" for program, _, _ in azure.calls))

    def test_invalid_polling_endpoint_is_rejected(self):
        module = load("polling")
        name = "config"
        for invalid in ("http://gateway.azure.com/triggerconfigs/config/receive", "https://127.0.0.1/api/triggerconfigs/config/receive",
                        "https://example.com/api/triggerconfigs/config/receive", "https://gateway.azure.com/api/triggerconfigs/other/receive"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                module.polling_endpoint(invalid, name)

    def test_detection_handles_first_provision_and_reprovision_without_reading_settings(self):
        for mode in MODES:
            for exists in (False, True):
                module, azure = load(mode), AzureDouble(mode, exists=exists)
                if mode == "webhook":
                    outputs = {key: value for key, value in azure.outputs.items() if key in ("AZURE_ENV_NAME", "AZURE_SUBSCRIPTION_ID")}
                else:
                    outputs = azure.outputs
                self.assertEqual(module.detect_app(outputs, run=azure), exists)
                self.assertEqual(azure.outputs["PLANNER_FUNCTION_APP_EXISTS"], str(exists).lower())
                self.assertFalse(azure.writes)
                with self.assertRaisesRegex(ValueError, "inventory"):
                    module.detect_app(outputs, run=lambda *arguments: {})

    def test_private_local_settings_preserve_bytes_force_replace_and_cleanup(self):
        for mode in MODES:
            module = load(mode)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "local.settings.json"
                path.write_bytes(b"existing bytes\r\n")
                self.assertFalse(module.write_local_settings(path, {"new": "value"}))
                self.assertEqual(path.read_bytes(), b"existing bytes\r\n")
                self.assertTrue(module.write_local_settings(path, {"new": "value"}, force=True))
                self.assertEqual(json.loads(path.read_text())["Values"], {"new": "value"})
                self.assertEqual([item.name for item in Path(directory).iterdir()], ["local.settings.json"])
                with self.assertRaisesRegex(ValueError, "regular file"):
                    module.regular_file(Path(directory))
            request = None

            def failing_request():
                nonlocal request
                with module.private_json({"secret": "synthetic"}) as argument:
                    request = Path(argument[1:])
                    self.assertTrue(request.exists())
                    raise RuntimeError("synthetic")

            self.assertRaisesRegex(RuntimeError, "synthetic", failing_request)
            self.assertIsNotNone(request)
            self.assertFalse(request.exists())

    def test_each_mode_can_be_copied_without_parent_files(self):
        for mode in MODES:
            with tempfile.TemporaryDirectory() as directory:
                standalone = Path(directory) / mode
                shutil.copytree(ROOT / mode, standalone, ignore=shutil.ignore_patterns(".azure", ".venv", "__pycache__", "local.settings.json", "trigger-inputs.json"))
                module = load(mode, root=Path(directory))
                with patch.dict(os.environ, {"PLANNER_TRIGGER_INPUTS": json.dumps(selection(module, FUNCTIONS[2:]))}):
                    self.assertEqual(module.select_inputs(standalone)[0]["parameters"], [])
                for path in (standalone / "infra/scripts").glob("postdeploy.*"):
                    self.assertNotIn("../../../", path.read_text())
                self.assertNotIn("../README", (standalone / "README.md").read_text())
                ignores = (standalone / ".gitignore").read_text()
                for name in ("local.settings.json", "trigger-inputs.json", ".azure/", ".planner-settings-*/"):
                    self.assertIn(name, ignores)

    def test_dependency_bundle_and_settings_contracts(self):
        for mode in MODES:
            project = ROOT / mode
            requirements = (project / "requirements.txt").read_text().splitlines()
            self.assertEqual(requirements, ['azure-functions>=1.27.0b1; python_version < "3.13"',
                                            'azure-functions>=2.4.0; python_version >= "3.13"',
                                            'azurefunctions-extensions-connectors>=1.0.0'])
            bundle = json.loads((project / "host.json").read_text())["extensionBundle"]
            self.assertEqual(bundle, {"id": "Microsoft.Azure.Functions.ExtensionBundle", "version": "[4.41.2, 5.0.0)"})
            self.assertEqual(json.loads((project / "local.settings.example.json").read_text())["Values"]["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
            app = (project / "infra" / ("app.bicep" if mode == "polling" else "main.bicep")).read_text()
            settings = (project / "infra/app-settings.bicep").read_text()
            self.assertIn("/config/appsettings', '2024-04-01').properties", app)
            self.assertNotIn("configs: [", app)
            self.assertIn("properties: union(existingAppSettings, {", settings)
            self.assertIn("@secure()\nparam existingAppSettings object", settings)
            self.assertNotIn("namespaceAccess", (project / "infra/connector-namespace.bicep").read_text())
            self.assertIn("developerAccess", (project / "infra/connector-namespace.bicep").read_text())
            self.assertIn("functionAccess", (project / "infra/function-access.bicep").read_text())


class RichBindingTests(unittest.TestCase):
    """Use the real Functions SDK and extension when installed in the test runtime."""

    def test_six_rich_bindings_convert_invoke_and_serialize_wire_metadata(self):
        try:
            from azurefunctions.extensions.base import Datum
            from azurefunctions.extensions.connectors.planner import ConnectorConverter, GetTaskResponseV2
        except ImportError as error:
            self.skipTest(f"Install the sample requirements for rich-binding execution: {error}")
        for mode in MODES:
            module = load(mode, "function_app.py")
            functions = module.app.get_functions()
            self.assertEqual({function.get_function_name() for function in functions}, set(FUNCTIONS))
            for function in functions:
                name = function.get_function_name()
                handler = function.get_user_function()
                annotation = typing.get_type_hints(handler)["tasks"]
                self.assertEqual(annotation, typing.List[GetTaskResponseV2])
                self.assertTrue(ConnectorConverter.check_input_type_annotation(annotation))
                binding, = json.loads(function.get_function_json())["bindings"]
                self.assertEqual(binding["direction"].lower(), "in")
                self.assertEqual(binding["name"], "tasks")
                self.assertEqual(binding["type"], "connectorTrigger")
                self.assertEqual(binding["connection"], "ConnectorNamespace")
                if mode == "polling":
                    self.assertEqual(binding["deliveryMode"], "Poll")
                    self.assertEqual(binding["triggerConfigName"], "%" + name + "TriggerConfigName%")
                else:
                    self.assertNotIn("deliveryMode", binding)
                    self.assertNotIn("triggerConfigName", binding)
                for records in ([], [{"id": "synthetic-task", "title": "DO-NOT-LOG", "percentComplete": 100}]):
                    payload = {"body": {"value": records}, "headers": {}, "statusCode": 200}
                    for value in (payload, json.dumps(payload), json.dumps(payload).encode()):
                        tasks = ConnectorConverter.decode(data=Datum(value=value, type="json"), trigger_metadata=None, pytype=annotation)
                        self.assertEqual(len(tasks), len(records))
                        if records:
                            self.assertEqual(tasks[0].id, "synthetic-task")
                            self.assertEqual(tasks[0].percent_complete, 100)
                        with self.assertLogs(level="INFO") as logs:
                            handler(tasks)
                        self.assertIn(f"{name} trigger ({len(records)} items)", logs.output[0])
                        self.assertNotIn("DO-NOT-LOG", str(logs.output))
                        self.assertNotIn("synthetic-task", str(logs.output))
                events = SimpleNamespace(string=[json.dumps({"body": {"id": "first"}}), json.dumps({"body": {"value": [{"id": "second"}]}})])
                tasks = ConnectorConverter.decode(data=Datum(value=events, type="collection_string"), trigger_metadata=None, pytype=annotation)
                self.assertEqual([task.id for task in tasks], ["first", "second"])


if __name__ == "__main__":
    unittest.main()