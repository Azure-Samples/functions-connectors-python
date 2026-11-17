# Copyright (c) Microsoft Corporation.  All rights reserved.
"""Offline Salesforce hook regressions; no test contacts Azure or Salesforce."""

from __future__ import annotations

import base64
import copy
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

SAMPLE = Path(__file__).resolve().parents[1]
MODES = ("polling", "webhook")


def load_helper(mode: str, root: Path = SAMPLE):
    """Import only a mode-local helper, with no parent package path."""
    path = root / mode / "infra/scripts/setup.py"
    specification = importlib.util.spec_from_file_location("salesforce_setup_" + mode, path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class Cloud:
    """Model ARM readbacks, consent and settings while rejecting unexpected calls."""

    def __init__(self, helper, mode: str):
        self.helper = helper
        self.mode = mode
        self.outputs = {
            "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000001",
            "resourceGroupName": "rg-demo", "functionAppName": "func-demo",
            "connectorNamespaceName": "cns-demo", "connectorNamespaceConnectionName": "cnsc-demo",
            "functionAppDefaultHostname": "func-demo.azurewebsites.net",
            "salesforceAuthenticationParameterSetName": "BasicAuthentication",
        }
        self.outputs["connectorNamespaceResourceId"] = (
            "/subscriptions/" + self.outputs["AZURE_SUBSCRIPTION_ID"]
            + "/resourceGroups/rg-demo/providers/Microsoft.Web/connectorGateways/cns-demo")
        self.root = helper.context(self.outputs)
        self.collection = self.root + "/triggerConfigs"
        self.resources = {}
        self.calls = []
        self.connected = True
        self.app_names = []
        self.settings = {"CUSTOM_SETTING": "preserve-me", "AzureWebJobs.OnSalesforceNewItems.Disabled": "true"}

    def trigger(self, function: str, **properties) -> dict:
        """Build an owned trigger with server-generated readiness metadata."""
        name = self.helper.trigger_name(self.outputs, function)
        values = {
            "metadata": self.helper.metadata(self.outputs, function),
            "connectionDetails": {"connectorName": "salesforce", "connectionName": "cnsc-demo"},
            "operationName": self.helper.OPERATIONS[function],
            "parameters": [{"name": "table", "value": "Account"}],
            "state": "Enabled", "provisioningState": "Succeeded",
        }
        if self.mode == "polling":
            values.update(deliveryMode="Poll", pollingEndpoints={
                "receiveUri": "https://events.example.com/api/connectorGateways/cns-demo/api/triggerConfigs/" + name + "/receive"})
        else:
            values["notificationDetails"] = {}
        values.update(properties)
        return {"id": self.outputs["connectorNamespaceResourceId"] + "/triggerConfigs/" + name,
                "name": name, "properties": values}

    def inputs(self, *functions: str) -> list[dict]:
        """Use reviewed object IDs rather than placeholders."""
        return [{"functionName": function, "operationName": self.helper.OPERATIONS[function],
                 "parameters": [{"name": "table", "value": "Account"}]} for function in functions]

    def rest(self, outputs, method, url, body=None):
        """Serve only the expected namespace and retain PUT properties exactly."""
        self.calls.append((method, url, copy.deepcopy(body)))
        if url == self.root + "/connections/cnsc-demo":
            return {"id": outputs["connectorNamespaceResourceId"] + "/connections/cnsc-demo", "properties": {
                "connectorName": "salesforce", "parameterValueSet": {"name": "BasicAuthentication"},
                "overallStatus": "Connected" if self.connected else "Error"}}
        if url.startswith(self.collection + "?"):
            return {"value": list(self.resources.values())}
        if url.startswith(self.collection + "/"):
            name = url.rsplit("/", 1)[1]
            if method == "put":
                self.resources[name] = self.trigger(next(
                    function for function in self.helper.OPERATIONS
                    if self.helper.trigger_name(outputs, function) == name))
                self.resources[name]["properties"].update(copy.deepcopy(body["properties"]))
            return copy.deepcopy(self.resources[name])
        raise AssertionError("Unexpected ARM call.")

    def cli(self, program, *arguments, interactive=False):
        """Simulate app/settings commands and persist only explicit azd env writes."""
        self.calls.append((program, arguments, interactive))
        if program == "azd":
            if arguments[:2] == ("env", "get-values"):
                return self.outputs
            if arguments[:2] == ("env", "set"):
                self.outputs[arguments[2]] = arguments[3]
                return None
        if program == "az":
            if arguments[:3] == ("connector-namespace", "connection", "authenticate"):
                self.connected = True
                return None
            if arguments[:2] == ("functionapp", "list"):
                return self.app_names
            if arguments[:2] == ("functionapp", "show"):
                return {"defaultHostName": self.outputs["functionAppDefaultHostname"]}
            if arguments[:3] == ("functionapp", "keys", "list"):
                return {"systemKeys": {"connector_extension": "test-system-key"}}
            if arguments[:4] == ("functionapp", "config", "appsettings", "list"):
                return [{"name": name, "value": value} for name, value in self.settings.items()]
            if arguments[:4] == ("functionapp", "config", "appsettings", "set"):
                path = Path(arguments[arguments.index("--settings") + 1][1:])
                self.settings = json.loads(path.read_text(encoding="utf-8"))
                return None
        raise AssertionError("Unexpected CLI call.")


@contextmanager
def fast_directory(parent=None):
    """Keep most mocked tests independent of platform ACL tooling."""
    with tempfile.TemporaryDirectory(dir=parent) as directory:
        yield Path(directory)


class SalesforceSetupTests(unittest.TestCase):
    """Run common safety regressions against both standalone helper copies."""

    def test_helpers_stay_identical(self):
        self.assertEqual((SAMPLE / "polling/infra/scripts/setup.py").read_bytes(),
                         (SAMPLE / "webhook/infra/scripts/setup.py").read_bytes())

    def test_legacy_entry_point_forwards_new_layer_arguments(self):
        specification = importlib.util.spec_from_file_location("legacy_salesforce_setup", SAMPLE / "scripts/setup.py")
        legacy = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(legacy)
        cloud = Cloud(load_helper("webhook"), "webhook")
        responses = [subprocess.CompletedProcess([], 0, stdout=json.dumps(cloud.outputs)),
                     subprocess.CompletedProcess([], 0, stdout="[]"),
                     subprocess.CompletedProcess([], 0, stdout="")]
        with patch.object(shutil, "which", side_effect=lambda name: name), \
                patch.object(subprocess, "run", side_effect=responses) as command:
            legacy.main(["--mode", "webhook", "--project", str(SAMPLE / "webhook"), "--phase", "app"])
        self.assertEqual(command.call_count, 3)
        self.assertEqual(command.call_args.args[0][-2:], ["SALESFORCE_FUNCTION_APP_EXISTS", "false"])

    def test_each_copied_mode_imports_without_parent_files(self):
        for mode in MODES:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(SAMPLE / mode, root / mode,
                                ignore=shutil.ignore_patterns(".azure", ".venv", "__pycache__", "local.settings.json"))
                module = load_helper(mode, root)
                self.assertEqual(len(module.OPERATIONS), 2)
                for script in (root / mode / "infra/scripts").glob("*"):
                    if script.suffix in (".sh", ".ps1"):
                        self.assertNotIn("../../../", script.read_text())
                self.assertNotRegex((root / mode / "README.md").read_text(), r"\]\(\.\./")

    def test_invalid_inputs_are_rejected(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            valid = cloud.inputs("OnSalesforceNewItems")
            invalid = [[], valid + valid, [{**valid[0], "operationName": "Other"}],
                       [{**valid[0], "parameters": []}], [{**valid[0], "extra": True}]]
            for value in ("", " ", "<REAL_SALESFORCE_OBJECT_ID>", " Account", None):
                invalid.append([{**valid[0], "parameters": [{"name": "table", "value": value}]}])
            for index, triggers in enumerate(invalid):
                with self.subTest(mode=mode, case=index), self.assertRaises(ValueError):
                    helper.validate_inputs(triggers)

    def test_json_rejects_duplicate_properties_and_nonfinite_numbers(self):
        for mode in MODES:
            for text in ('{"name":1,"name":2}', '{"value":NaN}', '{"value":Infinity}'):
                with self.subTest(mode=mode, text=text), self.assertRaises(ValueError):
                    load_helper(mode).read_json(text)

    def test_poll_registration_precedes_app_and_code_without_hostname(self):
        helper = load_helper("polling")
        cloud = Cloud(helper, "polling")
        cloud.outputs.pop("functionAppDefaultHostname")
        cloud.connected = False
        with patch.object(helper, "cli", side_effect=cloud.cli), patch.object(helper, "rest", side_effect=cloud.rest), \
                patch.object(helper, "collect_inputs", return_value=cloud.inputs("OnSalesforceNewItems")):
            helper.main(["--mode", "polling", "--project", str(SAMPLE / "polling"), "--phase", "triggers"])
        settings = json.loads(base64.b64decode(cloud.outputs["SALESFORCE_POLL_SETTINGS"]))
        self.assertEqual(settings["ConnectorNamespace__pollingEndpoint"], "https://events.example.com/api/connectorGateways/cns-demo")
        self.assertEqual(settings["AzureWebJobs.OnSalesforceNewItems.Disabled"], "false")
        self.assertEqual(settings["AzureWebJobs.OnSalesforceUpdatedItems.Disabled"], "true")
        self.assertFalse(any(call[0] == "az" and call[1][0] == "functionapp" for call in cloud.calls))
        consent = next(index for index, call in enumerate(cloud.calls) if call[0] == "az")
        put = next(index for index, call in enumerate(cloud.calls) if call[0] == "put")
        self.assertLess(consent, put)
        self.assertEqual(next(iter(cloud.resources.values()))["properties"]["deliveryMode"], "Poll")

    def test_failed_consent_does_not_create_sources(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            cloud.connected = False
            def no_consent(program, *arguments, **kwargs):
                if program == "azd":
                    return cloud.outputs
                return None
            with self.subTest(mode=mode), patch.object(helper, "cli", side_effect=no_consent), \
                    patch.object(helper, "rest", side_effect=cloud.rest), self.assertRaises(ValueError):
                helper.main(["--mode", mode, "--project", str(SAMPLE / mode),
                             "--phase", "triggers" if mode == "polling" else "postdeploy"])
            self.assertFalse(any(call[0] == "put" for call in cloud.calls))

    def test_connection_selector_or_id_mismatch_stops_consent(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            response = cloud.rest(cloud.outputs, "get", cloud.root + "/connections/cnsc-demo")
            for field in ("id", "selector", "connector"):
                invalid = copy.deepcopy(response)
                if field == "id":
                    invalid["id"] += "-foreign"
                elif field == "selector":
                    invalid["properties"]["parameterValueSet"]["name"] = "Other"
                else:
                    invalid["properties"]["connectorName"] = "Other"
                with self.subTest(mode=mode, field=field), patch.object(helper, "rest", return_value=invalid), \
                        patch.object(helper, "cli") as command, self.assertRaises(ValueError):
                    helper.authorize(cloud.outputs, cloud.root)
                command.assert_not_called()

    def test_foreign_deselected_source_blocks_every_write(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            resource = cloud.trigger("OnSalesforceUpdatedItems")
            resource["properties"]["metadata"]["functionAppName"] = "foreign-app"
            cloud.resources[resource["name"]] = resource
            with self.subTest(mode=mode), patch.object(helper, "rest", side_effect=cloud.rest), \
                    patch.object(helper, "cli") as command, self.assertRaises(ValueError):
                helper.configure(cloud.outputs, cloud.root, mode, cloud.inputs("OnSalesforceNewItems"))
            command.assert_not_called()
            self.assertFalse(any(call[0] == "put" for call in cloud.calls))

    def test_only_owned_deselected_sources_are_disabled_and_fields_survive(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            for function in helper.OPERATIONS:
                resource = cloud.trigger(function, custom={"null": None, "large": 2 ** 80})
                cloud.resources[resource["name"]] = resource
            unrelated = cloud.trigger("OnSalesforceNewItems")
            unrelated["name"] = "unrelated-source"
            unrelated["id"] = cloud.outputs["connectorNamespaceResourceId"] + "/triggerConfigs/unrelated-source"
            cloud.resources[unrelated["name"]] = unrelated
            with self.subTest(mode=mode), patch.object(helper, "rest", side_effect=cloud.rest), \
                    patch.object(helper, "cli", side_effect=cloud.cli), patch.object(helper, "private_directory", fast_directory):
                helper.configure(cloud.outputs, cloud.root, mode, cloud.inputs("OnSalesforceNewItems"))
                puts = [call for call in cloud.calls if call[0] == "put"]
                disabled = next(call[2]["properties"] for call in puts if call[1].endswith("onsalesforceupdateditems"))
                before = helper.writable(cloud.trigger("OnSalesforceUpdatedItems", custom={"null": None, "large": 2 ** 80}))
                self.assertEqual(disabled, {**before, "state": "Disabled"})
                self.assertEqual(cloud.resources["unrelated-source"], unrelated)
                for _, _, body in puts:
                    self.assertNotIn("pollingEndpoints", body["properties"])
                    self.assertNotIn("provisioningState", body["properties"])
                    self.assertEqual(body["properties"]["custom"], {"null": None, "large": 2 ** 80})
                cloud.calls.clear()
                helper.configure(cloud.outputs, cloud.root, mode, cloud.inputs("OnSalesforceNewItems"))
                self.assertFalse(any(call[0] == "put" for call in cloud.calls))

    def test_read_existing_then_merge_cloud_settings(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            with self.subTest(mode=mode), patch.object(helper, "cli", side_effect=cloud.cli), \
                    patch.object(helper, "private_directory", fast_directory):
                helper.save_cloud_settings(cloud.outputs, {"AzureWebJobs.OnSalesforceNewItems.Disabled": "false"})
            self.assertEqual(cloud.settings, {"CUSTOM_SETTING": "preserve-me", "AzureWebJobs.OnSalesforceNewItems.Disabled": "false"})
            self.assertEqual([call[1][3] for call in cloud.calls], ["list", "set"])

    def test_failed_settings_read_cannot_write_empty_replacement(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            for response in (None, {}, [{"name": "custom", "value": None}],
                             [{"name": "custom", "value": "a"}, {"name": "custom", "value": "b"}]):
                with self.subTest(mode=mode, response=response), patch.object(helper, "cli", return_value=response) as command, \
                        self.assertRaises(ValueError):
                    helper.save_cloud_settings(cloud.outputs, {})
                self.assertEqual(command.call_count, 1)

    def test_app_inventory_must_succeed_before_setting_exists_flag(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            for names, expected in (([], "false"), (["FUNC-DEMO", "other-app"], "true")):
                cloud.app_names = names
                with self.subTest(mode=mode, names=names), patch.object(helper, "cli", side_effect=cloud.cli):
                    helper.prepare_app(cloud.outputs)
                self.assertEqual(cloud.outputs["SALESFORCE_FUNCTION_APP_EXISTS"], expected)
            for response in (None, {}, ["func-demo", "FUNC-DEMO"]):
                with self.subTest(mode=mode, invalid=response), patch.object(helper, "cli", return_value=response) as command, \
                        self.assertRaises(ValueError):
                    helper.prepare_app(cloud.outputs)
                self.assertEqual(command.call_count, 1)
            with patch.object(helper, "cli", side_effect=RuntimeError("denied")) as command, self.assertRaises(RuntimeError):
                helper.prepare_app(cloud.outputs)
            self.assertEqual(command.call_count, 1)

    def test_poll_postdeploy_only_writes_validated_local_settings(self):
        helper = load_helper("polling")
        cloud = Cloud(helper, "polling")
        with patch.object(helper, "rest", side_effect=cloud.rest):
            settings = helper.configure(cloud.outputs, cloud.root, "polling", cloud.inputs("OnSalesforceNewItems"), apply_cloud=False)
        cloud.outputs["triggerConfigSettingsEncoded"] = base64.b64encode(json.dumps(settings).encode()).decode()
        with patch.object(helper, "cli", return_value=cloud.outputs), patch.object(helper, "rest") as rest, \
                patch.object(helper, "write_local_settings", return_value=True) as local:
            helper.main(["--mode", "polling", "--project", str(SAMPLE / "polling")])
        rest.assert_not_called()
        self.assertEqual(local.call_args.args[1], settings)
        for change in ({"CUSTOM_SETTING": "not-owned"}, {"ConnectorNamespace__pollingEndpoint": "http://unsafe.example.com"},
                       {"OnSalesforceNewItemsTriggerConfigName": "foreign"}):
            altered = {**settings, **change}
            cloud.outputs["triggerConfigSettingsEncoded"] = base64.b64encode(json.dumps(altered).encode()).decode()
            with self.subTest(change=change), self.assertRaises(ValueError):
                helper.poll_settings(cloud.outputs)

    def test_registration_failures_do_not_update_app_settings(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            for state in ("Failed", "Canceled", "Disabled"):
                result = cloud.trigger("OnSalesforceNewItems")
                if state == "Disabled":
                    result["properties"]["state"] = state
                else:
                    result["properties"]["provisioningState"] = state
                with self.subTest(mode=mode, state=state), patch.object(helper, "rest", return_value=result), \
                        patch.object(helper.time, "sleep"), self.assertRaises((ValueError, TimeoutError)):
                    helper.ready(cloud.outputs, cloud.collection, "OnSalesforceNewItems", mode)

    def test_pagination_checks_next_page_after_empty_first_page(self):
        for mode in MODES:
            helper = load_helper(mode)
            cloud = Cloud(helper, mode)
            next_url = cloud.collection + "?api-version=" + helper.API_VERSION + "&skip=next"
            resource = cloud.trigger("OnSalesforceNewItems")
            with patch.object(helper, "rest", side_effect=[{"value": [], "nextLink": next_url}, {"value": [resource]}]) as rest:
                self.assertEqual(helper.list_triggers(cloud.outputs, cloud.collection), [resource])
            self.assertEqual(rest.call_args.args[2], next_url)
            for next_link in (next_url.replace("management.azure.com", "other.example.com"),
                              cloud.collection + "?api-version=" + helper.API_VERSION):
                with self.subTest(mode=mode, link=next_link), patch.object(helper, "rest", return_value={"value": [], "nextLink": next_link}), \
                        self.assertRaises(ValueError):
                    helper.list_triggers(cloud.outputs, cloud.collection)

    def test_missing_webhook_key_and_hostname_mismatch_prevent_put(self):
        helper = load_helper("webhook")
        cloud = Cloud(helper, "webhook")
        for hostname, keys in ((cloud.outputs["functionAppDefaultHostname"], {"systemKeys": {}}),
                               ("wrong.example.com", {"systemKeys": {"connector_extension": "unused"}})):
            def command(program, *arguments, **kwargs):
                return {"defaultHostName": hostname} if arguments[1] == "show" else keys
            with self.subTest(hostname=hostname), patch.object(helper, "rest", side_effect=cloud.rest), \
                    patch.object(helper, "cli", side_effect=command), patch.object(helper.time, "sleep"), self.assertRaises(ValueError):
                helper.configure(cloud.outputs, cloud.root, "webhook", cloud.inputs("OnSalesforceNewItems"))
            self.assertFalse(any(call[0] == "put" for call in cloud.calls))

    def test_local_settings_isolation_preservation_and_no_cloud_credential(self):
        for mode in MODES:
            helper = load_helper(mode)
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory).resolve() / "local.settings.json"
                cloud = {"ConnectorNamespace__credential": "managedidentity", "AzureWebJobs.OnSalesforceNewItems.Disabled": "false"}
                self.assertTrue(helper.write_local_settings(path, cloud))
                values = json.loads(path.read_text())["Values"]
                self.assertEqual(values["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
                self.assertNotIn("ConnectorNamespace__credential", values)
                path.write_bytes(b"existing bytes\n")
                self.assertFalse(helper.write_local_settings(path, cloud))
                self.assertEqual(path.read_bytes(), b"existing bytes\n")
                self.assertTrue(helper.write_local_settings(path, cloud, force=True))
                self.assertEqual(list(path.parent.glob("salesforce-hook-*")), [])

    def test_private_request_cleanup_on_failure(self):
        for mode in MODES:
            helper = load_helper(mode)
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                with helper.private_json({"secret": "test-only"}) as argument:
                    path = Path(argument[1:])
                    self.assertEqual(json.loads(path.read_text()), {"secret": "test-only"})
                    raise RuntimeError("simulated failure")
            self.assertFalse(path.exists())

    def test_dependency_bundle_and_access_policy_contracts(self):
        for mode in MODES:
            folder = SAMPLE / mode
            requirements = (folder / "requirements.txt").read_text().splitlines()
            self.assertEqual(requirements, ['azure-functions>=1.27.0b1; python_version < "3.13"',
                                            'azure-functions>=2.4.0; python_version >= "3.13"',
                                            'azurefunctions-extensions-connectors>=1.0.0'])
            self.assertEqual(json.loads((folder / "host.json").read_text())["extensionBundle"],
                             {"id": "Microsoft.Azure.Functions.ExtensionBundle", "version": "[4.41.2, 5.0.0)"})
            self.assertNotIn("namespace-msi", (folder / "infra/connector-namespace.bicep").read_text())
            self.assertIn("name: 'dev-user'", (folder / "infra/connector-namespace.bicep").read_text())
            self.assertIn("name: 'functionapp-msi'", (folder / "infra/function-access.bicep").read_text())
            self.assertIn("list(", (folder / "infra/app.bicep").read_text())
            self.assertIn("union(existingAppSettings", (folder / "infra/app-settings.bicep").read_text())
            self.assertEqual(json.loads((folder / "local.settings.example.json").read_text())["Values"]["PYTHON_ISOLATE_WORKER_DEPENDENCIES"], "1")
            self.assertIn("local.settings.json", (folder / ".gitignore").read_text())
            self.assertIn("local.settings*.json", (folder / ".funcignore").read_text())

    def test_platform_wrappers_work_from_a_standalone_path_with_spaces(self):
        shells = []
        if shutil.which("pwsh"):
            shells.append(("pwsh", [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-File"]))
        bash = Path(r"C:\Program Files\Git\bin\bash.exe") if os.name == "nt" else Path(shutil.which("sh") or "/bin/sh")
        if bash.is_file():
            shells.append(("sh", [str(bash)]))
        self.assertTrue(shells, "A supported platform shell is required for wrapper validation.")
        for mode in MODES:
            for shell, command in shells:
                with self.subTest(mode=mode, shell=shell), tempfile.TemporaryDirectory(prefix="salesforce copy ") as directory:
                    root = Path(directory).resolve()
                    project = root / mode
                    shutil.copytree(SAMPLE / mode / "infra/scripts", project / "infra/scripts",
                                    ignore=shutil.ignore_patterns("__pycache__"))
                    (project / "infra/scripts/setup.py").write_text("import json,sys; print(json.dumps(sys.argv[1:]))", encoding="utf-8")
                    scripts = ["postdeploy", "prepare-app"] + (["prepare-triggers"] if mode == "polling" else [])
                    for script in scripts:
                        extension = "ps1" if shell == "pwsh" else "sh"
                        result = subprocess.run(command + [str(project / f"infra/scripts/{script}.{extension}")],
                                                env={**os.environ, "PYTHON": sys.executable}, cwd=root,
                                                capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        arguments = json.loads(result.stdout)
                        self.assertEqual(arguments[:2], ["--mode", mode])
                        self.assertEqual(Path(arguments[3]).resolve(), project)
                        if script != "postdeploy":
                            self.assertEqual(arguments[-2:], ["--phase", "app" if script == "prepare-app" else "triggers"])


if __name__ == "__main__":
    unittest.main()