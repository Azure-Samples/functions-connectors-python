import base64
import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
FUNCTION = "OnAzureDevOpsGitPush"
OPERATIONS = {FUNCTION: "OnGitPush", "OnAzureDevOpsBuildCompleted": "OnBuildCompleted"}


def load_mode(mode):
    scripts = ROOT / mode / "infra" / "scripts"
    spec = importlib.util.spec_from_file_location(f"{mode}_trigger_inputs", scripts / "trigger_inputs.py")
    trigger_inputs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trigger_inputs)
    spec = importlib.util.spec_from_file_location(f"{mode}_setup", scripts / "setup.py")
    setup = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"trigger_inputs": trigger_inputs}):
        spec.loader.exec_module(setup)
    return trigger_inputs, setup


def swagger():
    def picker(operation, parameters=None):
        return {
            "operationId": operation,
            "parameters": parameters or {},
            "value-collection": "data/items",
            "value-path": "id",
            "value-title": "name",
        }

    return {
        "paths": {
            "/{connectionId}/subscriptions": {
                "get": {
                    "operationId": "OnGitPush",
                    "parameters": [
                        {"name": "project", "in": "query", "type": "string", "required": True,
                         "x-ms-dynamic-values": picker("GetProjects", {"account": {"parameter": "account"}})},
                        {"name": "account", "in": "query", "type": "string", "required": True,
                         "x-ms-dynamic-values": picker("GetAccounts")},
                        {"name": "repository", "in": "query", "type": "string", "required": True,
                         "x-ms-dynamic-values": picker("GetRepositories", {
                             "account": {"parameter": "account"}, "project": {"parameter": "project"}})},
                        {"name": "branch", "in": "query", "type": "string", "enum": ["main", "release"]},
                    ],
                }
            },
            "/{connectionId}/accounts": {
                "get": {"operationId": "GetAccounts", "parameters": []}
            },
            "/{connectionId}/projects/{account}": {
                "get": {
                    "operationId": "GetProjects",
                    "parameters": [
                        {"name": "connectionId", "in": "path", "required": True},
                        {"name": "account", "in": "path", "required": True, "x-ms-url-encoding": "double"},
                        {"name": "filter", "in": "query"},
                    ],
                }
            },
            "/{connectionId}/repositories/{account}/{project}": {
                "get": {
                    "operationId": "GetRepositories",
                    "parameters": [
                        {"name": "account", "in": "path", "required": True},
                        {"name": "project", "in": "path", "required": True},
                    ],
                }
            },
        }
    }


class TriggerInputTests(unittest.TestCase):
    def test_authenticated_pickers_resolve_dependencies_and_optional_filters(self):
        for mode in ("polling", "webhook"):
            with self.subTest(mode=mode):
                inputs, _ = load_mode(mode)
                calls = []

                def invoke(operation, values):
                    calls.append((operation, values))
                    return {"data": {"items": [{"id": operation, "name": operation + " label"}]}}

                def choose(label, choices):
                    if label.startswith("Configure OnAzureDevOps"):
                        return FUNCTION in label
                    if label.startswith("Configure branch"):
                        return True
                    return choices[0][1]

                def prompt(_label):
                    self.fail("A picker should be used instead of requesting a raw identifier")

                selected = inputs.collect_trigger_inputs(
                    swagger(), OPERATIONS, invoke, choose=choose, prompt=prompt,
                    optional_filters=mode == "polling",
                )
                self.assertEqual(selected[0]["functionName"], FUNCTION)
                self.assertEqual(selected[0]["operationName"], "OnGitPush")
                values = {item["name"]: item["value"] for item in selected[0]["parameters"]}
                self.assertEqual(values["account"], "GetAccounts")
                self.assertEqual(values["project"], "GetProjects")
                self.assertEqual(values["repository"], "GetRepositories")
                self.assertEqual("branch" in values, mode == "polling")
                self.assertEqual(calls, [
                    ("GetAccounts", {}),
                    ("GetProjects", {"account": "GetAccounts"}),
                    ("GetRepositories", {"account": "GetAccounts", "project": "GetProjects"}),
                ])

    def test_picker_requests_encode_paths_and_cache_results(self):
        for mode in ("polling", "webhook"):
            with self.subTest(mode=mode):
                inputs, _ = load_mode(mode)
                request = inputs.operation_request(swagger(), "GetProjects", {"account": "a/b", "filter": "active"})
                self.assertEqual(request, {
                    "method": "GET", "path": "/projects/a%252Fb", "queries": {"filter": "active"},
                })
                requests = []
                invoke = inputs.make_picker(
                    swagger(), lambda body: requests.append(body) or {
                        "response": {"statusCode": 200, "body": '{"value": ["project"]}'}
                    },
                )
                self.assertEqual(invoke("GetProjects", {"account": "a/b"}), {"value": ["project"]})
                self.assertEqual(invoke("GetProjects", {"account": "a/b"}), {"value": ["project"]})
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0]["request"]["path"], "/projects/a%252Fb")

    def test_empty_or_invalid_picker_results_never_guess_inputs(self):
        for mode in ("polling", "webhook"):
            with self.subTest(mode=mode):
                inputs, _ = load_mode(mode)
                with self.assertRaisesRegex(ValueError, "choices|trigger"):
                    inputs.collect_trigger_inputs(
                        swagger(), OPERATIONS, lambda *_: {"data": {"items": []}},
                        choose=lambda label, choices: FUNCTION in label,
                        prompt=lambda _: self.fail("Unexpected manual prompt"),
                        optional_filters=mode == "polling", skip_unavailable=mode == "webhook",
                    )

    def test_saved_selections_are_reused_without_reprompting(self):
        selection = [{
            "functionName": FUNCTION, "operationName": "OnGitPush",
            "parameters": [{"name": "account", "value": "org"}, {"name": "project", "value": "project"},
                           {"name": "repository", "value": "repo"}],
        }]
        encoded = base64.b64encode(json.dumps(selection).encode()).decode()
        for mode, setting in (("polling", "POLLING_TRIGGER_INPUTS"),
                              ("webhook", "AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                _, setup = load_mode(mode)
                with patch.object(setup, "cli", return_value={setting: encoded}), patch.object(setup, "setup") as run:
                    setup.main(["--mode", mode, "--project", directory])
                self.assertEqual(run.call_args.args[1], selection)

    def test_input_file_overrides_saved_selections(self):
        file_selection = [{"functionName": "OnAzureDevOpsBuildCompleted",
                           "operationName": "OnBuildCompleted", "parameters": []}]
        saved = base64.b64encode(json.dumps([{
            "functionName": FUNCTION, "operationName": "OnGitPush", "parameters": [],
        }]).encode()).decode()
        for mode, setting in (("polling", "POLLING_TRIGGER_INPUTS"),
                              ("webhook", "AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                Path(directory, "trigger-inputs.json").write_text(json.dumps(file_selection))
                _, setup = load_mode(mode)
                with patch.object(setup, "cli", return_value={setting: saved}), patch.object(setup, "setup") as run:
                    setup.main(["--mode", mode, "--project", directory])
                self.assertEqual(run.call_args.args[1], file_selection)

    def test_invalid_saved_selection_stops_before_registration(self):
        for mode, setting in (("polling", "POLLING_TRIGGER_INPUTS"),
                              ("webhook", "AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                _, setup = load_mode(mode)
                with patch.object(setup, "cli", return_value={setting: "not-base64!"}), \
                        patch.object(setup, "setup") as run, self.assertRaisesRegex(ValueError, setting):
                    setup.main(["--mode", mode, "--project", directory])
                run.assert_not_called()

    def test_webhook_provisioning_needs_no_manual_input_file(self):
        _, setup = load_mode("webhook")
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(setup, "cli", return_value={}), patch.object(setup, "detect_app") as detect:
                setup.main(["--mode", "webhook", "--project", directory, "--phase", "prepare-app"])
            detect.assert_called_once()

    def test_live_schema_controls_required_fields(self):
        selection = [{
            "functionName": FUNCTION, "operationName": "OnGitPush",
            "parameters": [{"name": "account", "value": "org"}, {"name": "project", "value": "project"}],
        }]
        definition = swagger()
        definition["paths"]["/{connectionId}/subscriptions"]["get"]["parameters"][2]["required"] = False
        for mode in ("polling", "webhook"):
            with self.subTest(mode=mode):
                _, setup = load_mode(mode)
                self.assertEqual(setup.validate_inputs(selection, definition)[FUNCTION], selection[0]["parameters"])
                with self.assertRaisesRegex(ValueError, "required"):
                    setup.validate_inputs([{**selection[0], "parameters": selection[0]["parameters"][:1]}], definition)

    def test_interactive_setup_registers_and_saves_the_selection(self):
        for mode, setting in (("polling", "POLLING_TRIGGER_INPUTS"),
                              ("webhook", "AZURE_DEVOPS_WEBHOOK_TRIGGER_INPUTS")):
            with self.subTest(mode=mode):
                _, setup = load_mode(mode)
                outputs = {
                    "resourceGroupName": "rg-demo", "functionAppName": "func-demo",
                    "connectorNamespaceName": "cn-demo",
                    "connectorNamespaceResourceId": (
                        "/subscriptions/sub-1/resourceGroups/rg-demo/providers/Microsoft.Web/connectorGateways/cn-demo"
                    ),
                    "connectorNamespaceConnectionName": "azuredevops-demo-entra",
                    "CONNECTOR_NAMESPACE_LOCATION": "brazilsouth", "deliveryMode": mode,
                    "AZURE_SUBSCRIPTION_ID": "sub-1", "FUNCTION_APP_HOSTNAME": "func.example.com",
                }
                saved, requests, writes, app_settings = {}, [], [], []

                def run(program, arguments, **_kwargs):
                    if program == "azd" and arguments[:2] == ["env", "set"]:
                        saved[arguments[2]] = arguments[3]
                    if program == "az" and arguments[:3] == ["functionapp", "keys", "list"]:
                        return {"systemKeys": {"connector_extension": "test-key"}}
                    if program == "az" and arguments[:4] == ["functionapp", "config", "appsettings", "set"]:
                        path = arguments[arguments.index("--settings") + 1]
                        app_settings.append(json.loads(Path(path[1:]).read_text()))
                    return None

                def rest(_run, ctx, method, url, body=None):
                    if "managedApis/" in url:
                        return {"properties": {"apiDefinitions": {"value": swagger()}}}
                    if method == "POST" and url.endswith("/dynamicInvoke"):
                        requests.append(body["request"])
                        path = body["request"]["path"]
                        value = "org" if path == "/accounts" else "project" if path.startswith("/projects/") else "repo"
                        return {"response": {"statusCode": 200, "body": {"data": {"items": [{"id": value, "name": value}]}}}}
                    if method == "GET" and "/providers/Microsoft.Web/sites/" in url:
                        return {"properties": {"defaultHostName": "func.example.com"}}
                    if method == "PUT":
                        name = url.rsplit("/", 1)[-1]
                        properties = copy.deepcopy(body["properties"])
                        if mode == "polling":
                            properties["pollingEndpoints"] = {
                                "receiveUri": f"https://gateway.example.com/api/triggerconfigs/{name}/receive"
                            }
                        resource = {"id": urlsplit(url).path, "name": name, "properties": properties}
                        writes.append(resource)
                        return resource
                    self.fail(f"Unexpected {method} request to {url}")

                answers = iter(["1", "1", "1", "2", "1", "1", "1", "1", "1", "1", "1", "1", "1"])
                with patch.object(setup, "authorize", return_value={"properties": {
                    "connectionRuntimeUrl": "https://runtime.example.com/connection",
                }}), patch.object(setup, "rest", side_effect=rest), patch.object(setup, "list_triggers", return_value=[]), \
                        patch.object(setup, "write_local"), contextlib.redirect_stdout(io.StringIO()):
                    setup.setup(outputs, None, mode, ROOT / mode, run=run, prompt=lambda _: next(answers))

                selected = json.loads(base64.b64decode(saved[setting]))
                self.assertEqual([item["functionName"] for item in selected], [FUNCTION])
                self.assertEqual(len(requests), 3)
                if mode == "polling":
                    self.assertEqual(writes, [])
                    plan = json.loads(base64.b64decode(saved["POLLING_TRIGGER_PLAN"]))
                    self.assertEqual([item["name"] for item in plan["selected"]],
                                     [f"azuredevops-demo-entra-{FUNCTION.lower()}"])
                    properties = plan["selected"][0]["properties"]
                    self.assertEqual(properties["operationName"], "OnGitPush")
                    self.assertEqual(properties["deliveryMode"], "Poll")
                    self.assertNotIn("notificationDetails", properties)
                    flags = plan["settings"]
                    self.assertEqual(flags[f"AzureWebJobs.{FUNCTION}.Disabled"], "false")
                    self.assertEqual(flags["AzureWebJobs.OnAzureDevOpsBuildCompleted.Disabled"], "true")
                else:
                    self.assertEqual(len(writes), 1)
                    self.assertEqual(writes[0]["properties"]["operationName"], "OnGitPush")
                    self.assertIn(f"functionName={FUNCTION}", writes[0]["properties"]["notificationDetails"]["callbackUrl"])
                    self.assertEqual(app_settings[-1][f"AzureWebJobs.{FUNCTION}.Disabled"], "false")
                    self.assertEqual(app_settings[-1]["AzureWebJobs.OnAzureDevOpsBuildCompleted.Disabled"], "true")
                    self.assertEqual(app_settings[-1]["AzureDevOpsConnection"], "https://runtime.example.com/connection")

    @unittest.skipUnless(importlib.util.find_spec("azure"), "Sample dependencies are not installed")
    def test_bindings_and_local_settings_match_configured_triggers(self):
        expected = {
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
        for mode in ("polling", "webhook"):
            with self.subTest(mode=mode):
                _, setup = load_mode(mode)
                spec = importlib.util.spec_from_file_location(f"{mode}_function_app", ROOT / mode / "function_app.py")
                app = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(app)
                functions = app.app.get_functions()
                self.assertEqual(setup.OPERATIONS, expected)
                self.assertEqual({function.get_function_name() for function in functions}, set(expected))
                values = json.loads((ROOT / mode / "local.settings.example.json").read_text())["Values"]
                for function in functions:
                    name = function.get_function_name()
                    binding = json.loads(function.get_function_json())["bindings"][0]
                    self.assertEqual(values[f"AzureWebJobs.{name}.Disabled"], "true")
                    if mode == "polling":
                        self.assertEqual(binding["deliveryMode"], "Poll")
                        self.assertEqual(binding["triggerConfigName"], f"%{name}TriggerConfigName%")
                        self.assertIn(f"{name}TriggerConfigName", values)
                    else:
                        self.assertEqual(binding["connection"], "AzureDevOpsConnection")
                        self.assertIn("AzureDevOpsConnection", values)


if __name__ == "__main__":
    unittest.main()
