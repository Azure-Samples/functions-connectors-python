import base64
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "teamsApp/polling/infra/scripts"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inputs = load("sample_trigger_inputs", SCRIPTS / "trigger_inputs.py")
with patch.dict(sys.modules, {"trigger_inputs": inputs}):
    setup = load("sample_trigger_setup", SCRIPTS / "trigger_setup.py")


def picker(operation_id, parameters=None):
    return {"operationId": operation_id, "parameters": parameters or {},
            "value-collection": "items", "value-path": "id", "value-title": "name"}


class TriggerInputTests(unittest.TestCase):
    def test_selected_triggers_get_independent_dependent_picker_answers(self):
        swagger = {"paths": {"/subscribe": {"post": {"operationId": "Subscribe", "parameters": [
            {"name": "channel", "in": "query", "type": "string", "required": True,
             "x-ms-dynamic-values": picker("Channels", {"team": {"parameter": "team"}})},
            {"name": "team", "in": "query", "type": "string",
             "x-ms-dynamic-values": picker("Teams")},
            {"name": "filter", "in": "query", "type": "string"},
        ]}}}}
        calls = []

        def invoke(operation, values):
            calls.append((operation, copy.deepcopy(values)))
            return {"items": [{"id": operation + str(len(calls)), "name": operation}]}

        def choose(label, choices):
            if "(optional)" in label:
                return False
            if label == "Configure Skip?":
                return False
            return choices[-1][1] if label.startswith("Configure ") else choices[0][1]

        definitions = [{"functionName": name, "operationName": "Subscribe"} for name in ("First", "Skip", "Last")]
        selected = inputs.collect_trigger_inputs(swagger, definitions, invoke, choose=choose,
                                                  prompt=lambda _: self.fail("Picker inputs should not request raw IDs"))
        self.assertEqual([item["functionName"] for item in selected], ["First", "Last"])
        self.assertEqual(calls, [("Teams", {}), ("Channels", {"team": "Teams1"}),
                                 ("Teams", {}), ("Channels", {"team": "Teams3"})])
        self.assertNotEqual(selected[0]["parameters"], selected[1]["parameters"])
        self.assertTrue(all(parameter["name"] != "filter" for item in selected for parameter in item["parameters"]))

    def test_nested_dynamic_body_resolves_later_prerequisite_and_keeps_types(self):
        swagger = {"paths": {"/subscribe": {"post": {"operationId": "Subscribe", "parameters": [
            {"name": "requestBody", "in": "body", "schema": {"type": "object", "required": ["details", "count", "enabled"],
             "properties": {
                 "details": {"type": "object", "x-ms-dynamic-schema": {
                     "operationId": "Schema", "parameters": {"kind": {"parameterReference": "requestBody/kind"}},
                     "value-path": "schema"}},
                 "kind": {"type": "string", "enum": ["chat", "channel"]},
                 "count": {"type": "integer", "minimum": 1},
                 "enabled": {"type": "boolean"},
                 "callback": {"type": "string", "x-ms-notification-url": True},
                 "internal": {"type": "string", "x-ms-visibility": "internal", "default": "fixed"},
             }}},
        ]}}}}
        calls = []

        def invoke(operation, values):
            calls.append((operation, values))
            return {"schema": {"type": "object", "required": ["ids"], "properties": {
                "ids": {"type": "array", "maxItems": 1, "items": {"type": "string",
                        "x-ms-dynamic-list": picker("Items")}}}}} if operation == "Schema" else {
                            "items": [{"id": "actual-id", "name": "Item"}]}

        selected = inputs.collect_trigger_inputs(swagger, [{"functionName": "Event", "operationName": "Subscribe"}],
                                                  invoke, choose=lambda label, choices: choices[-1 if label.startswith("Configure ") else 0][1],
                                                  prompt=lambda _: "2")
        body = selected[0]["parameters"][0]["value"]
        self.assertEqual(calls[0], ("Schema", {"kind": "chat"}))
        self.assertEqual(body["details"], {"ids": ["actual-id"]})
        self.assertEqual(body["count"], 2)
        self.assertIs(body["enabled"], True)
        self.assertEqual(body["internal"], "fixed")
        self.assertNotIn("callback", body)

    def test_partial_body_defaults_do_not_skip_required_fields(self):
        swagger = {"paths": {"/subscribe": {"post": {"operationId": "Subscribe", "parameters": [
            {"name": "body", "in": "body", "schema": {"type": "object", "required": ["table", "scope"],
             "properties": {"table": {"type": "string"}, "scope": {"type": "integer"}}}},
        ]}}}}
        definition = {"functionName": "Event", "operationName": "Subscribe", "values": {"body": {"scope": 4}}}
        selected = inputs.collect_trigger_inputs(swagger, [definition], None,
                                                  choose=lambda _, choices: True, prompt=lambda _: "accounts")
        self.assertEqual(selected[0]["parameters"], [{"name": "body", "value": {"scope": 4, "table": "accounts"}}])
        self.assertEqual(definition["values"]["body"], {"scope": 4})

    def test_picker_requests_preserve_headers_body_and_double_encoded_paths(self):
        swagger = {"paths": {"/{connectionId}/tables/{id}": {"post": {"operationId": "Picker", "parameters": [
            {"name": "id", "in": "path", "required": True, "x-ms-url-encoding": "double"},
            {"name": "organization", "in": "header", "required": True},
            {"name": "query", "in": "query"}, {"name": "request", "in": "body"},
        ]}}}}
        request = inputs.operation_request(swagger, "Picker", {"id": "a/b", "organization": "org", "query": True, "request": {}})
        self.assertEqual(request, {"method": "POST", "path": "/tables/a%252Fb", "headers": {"organization": "org"},
                                   "queries": {"query": True}, "body": {}})

    def test_designer_only_address_picker_accepts_explicit_mailbox_input(self):
        swagger = {"paths": {"/subscribe": {"get": {"operationId": "Subscribe", "parameters": [
            {"name": "mailboxAddress", "in": "query", "type": "string", "required": True,
             "x-ms-dynamic-values": {"builtInOperation": "AadGraph.GetUsers", "value-path": "mail"}},
        ]}}}}
        selected = inputs.collect_trigger_inputs(swagger, [{"functionName": "Event", "operationName": "Subscribe"}],
                                                  lambda *_: self.fail("A designer-only picker cannot be invoked"),
                                                  choose=lambda *_: True, prompt=lambda _: "test@example.invalid")
        self.assertEqual(selected[0]["parameters"], [{"name": "mailboxAddress", "value": "test@example.invalid"}])

    def test_folder_tree_uses_selected_mailbox_and_connector_returned_folder_id(self):
        tree = {"open": {"operationId": "Open", "parameters": {"mailbox": {"parameterReference": "mailbox"}},
                         "itemsPath": "value", "itemTitlePath": "Name", "itemValuePath": "Id"},
                "browse": {"operationId": "Browse", "parameters": {
                    "mailbox": {"parameterReference": "mailbox"}, "id": {"selectedItemValuePath": "Id"}},
                    "itemsPath": "value", "itemTitlePath": "Name", "itemValuePath": "Id"}}
        swagger = {"paths": {"/subscribe": {"get": {"operationId": "Subscribe", "parameters": [
            {"name": "folder", "in": "query", "type": "string", "required": True, "x-ms-dynamic-tree": tree},
            {"name": "mailbox", "in": "query", "type": "string"},
        ]}}}}
        calls = []

        def invoke(operation, values):
            calls.append((operation, values))
            return {"value": [{"Name": "Inbox", "Id": "actual-id", "IsFolder": True}]} if operation == "Open" else {"value": []}

        selected = inputs.collect_trigger_inputs(swagger, [{"functionName": "Event", "operationName": "Subscribe"}],
                                                  invoke, choose=lambda label, choices: True if label.startswith("Configure ") else choices[0][1],
                                                  prompt=lambda _: "test@example.invalid")
        self.assertEqual(calls, [("Open", {"mailbox": "test@example.invalid"}),
                                 ("Browse", {"mailbox": "test@example.invalid", "id": "actual-id"})])
        self.assertIn({"name": "folder", "value": "actual-id"}, selected[0]["parameters"])

    def test_body_picker_can_reference_sibling_without_body_prefix(self):
        swagger = {"paths": {"/subscribe": {"post": {"operationId": "Subscribe", "parameters": [
            {"name": "subscriptionRequest", "in": "body", "schema": {"type": "object", "required": ["action"],
             "properties": {
                 "action": {"type": "string", "x-ms-dynamic-values": picker("Actions", {"table": {"parameter": "table"}})},
                 "table": {"type": "string", "enum": ["account"]},
             }}},
        ]}}}}
        calls = []

        def invoke(operation, values):
            calls.append((operation, values))
            return {"items": [{"id": "action-id", "name": "Action"}]}

        selected = inputs.collect_trigger_inputs(swagger, [{"functionName": "Event", "operationName": "Subscribe"}],
                                                  invoke, choose=lambda label, choices: True if label.startswith("Configure ") else choices[0][1])
        self.assertEqual(calls, [("Actions", {"table": "account"})])
        self.assertEqual(selected[0]["parameters"][0]["value"], {"table": "account", "action": "action-id"})

    def test_skip_all_and_unsupported_schema_fail_without_guessed_values(self):
        definition = [{"functionName": "Event", "operationName": "Subscribe"}]
        with self.assertRaisesRegex(ValueError, "at least one"):
            inputs.collect_trigger_inputs({}, definition, None, choose=lambda *_: False)
        swagger = {"paths": {"/": {"get": {"operationId": "Subscribe", "parameters": [
            {"name": "unknown", "in": "query", "type": "file", "required": True},
        ]}}}}
        with self.assertRaisesRegex(ValueError, "Unsupported input"):
            inputs.collect_trigger_inputs(swagger, definition, None, choose=lambda *_: True, prompt=lambda _: "unused")


class FakeAzure:
    def __init__(self, outputs):
        self.outputs, self.resources, self.writes, self.settings = outputs, {}, [], {}

    def run(self, program, *arguments, **_kwargs):
        if program == "azd":
            self.outputs[arguments[2]] = arguments[3]
            return None
        if arguments[:4] == ("functionapp", "config", "appsettings", "set"):
            self.settings.update(json.loads(Path(arguments[arguments.index("--settings") + 1][1:]).read_text()))
            return None
        if arguments[:3] == ("functionapp", "keys", "list"):
            return {"systemKeys": {"connector_extension": "private-key"}}
        if arguments[0] != "rest":
            raise AssertionError(arguments)
        url = arguments[arguments.index("--url") + 1].split("?")[0]
        method = arguments[arguments.index("--method") + 1]
        if url.endswith("/sites/app"):
            return {"properties": {"defaultHostName": "app.azurewebsites.net"}}
        if url.endswith("/triggerConfigs"):
            return {"value": copy.deepcopy(list(self.resources.values()))}
        if method == "PUT":
            properties = json.loads(Path(arguments[arguments.index("--body") + 1][1:]).read_text())["properties"]
            if properties.get("deliveryMode") == "Poll":
                properties["pollingEndpoints"] = {"receiveUri": "https://gateway.test/api/triggerconfigs/" + url.rsplit("/", 1)[1] + "/receive"}
            resource = {"name": url.rsplit("/", 1)[1], "id": url.removeprefix("https://management.azure.com"), "properties": properties}
            self.resources[url] = resource
            self.writes.append(copy.deepcopy(resource))
        return copy.deepcopy(self.resources[url])


class SetupTests(unittest.TestCase):
    def create(self, directory, mode="polling"):
        project = Path(directory) / mode
        project.mkdir()
        outputs = {"AZURE_SUBSCRIPTION_ID": "sub", "resourceGroupName": "rg", "connectorNamespaceName": "namespace",
                   "connectorNamespaceConnectionName": "connection", "functionAppName": "app",
                   "functionAppDefaultHostname": "app.azurewebsites.net"}
        config = {"connectorName": "teams", "namePrefix": "teams", "triggers": [
            {"functionName": "First", "operationName": "Subscribe"},
            {"functionName": "Second", "operationName": "Subscribe"},
        ]}
        fake = FakeAzure(outputs)
        subject = setup.Setup(project, config, outputs, run=fake.run, wait=lambda _: None)
        return subject, fake

    def test_poll_plan_only_provisions_selected_changes_and_reuses_endpoint_on_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            subject, fake = self.create(directory)
            selected = [{"functionName": "Second", "operationName": "Subscribe", "parameters": [{"name": "group", "value": "id"}]}]
            subject.configure(selected)
            document = json.loads(base64.b64decode(fake.outputs["POLLING_TRIGGER_PLAN"]))
            self.assertEqual([item["name"] for item in document["selected"]], ["teams-second"])
            self.assertEqual(document["settings"]["AzureWebJobs.First.Disabled"], "true")
            for item in document["selected"]:
                subject.rest("PUT", subject.collection + "/" + item["name"], {"properties": item["properties"]})
            subject.configure(selected)
            retry = json.loads(base64.b64decode(fake.outputs["POLLING_TRIGGER_PLAN"]))
            self.assertEqual(retry["selected"], [])
            self.assertEqual(retry["endpointConfigName"], "teams-second")
            self.assertEqual(subject.verify(selected), "https://gateway.test")
            self.assertEqual(len(fake.writes), 1)

    def test_deselection_disables_owned_config_without_deletion_and_foreign_config_blocks_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            subject, fake = self.create(directory)
            first = subject.config["triggers"][0]
            subject.rest("PUT", subject.collection + "/" + subject.name(first), {"properties": subject.properties(first, [])})
            selected = [{"functionName": "Second", "operationName": "Subscribe", "parameters": []}]
            subject.configure(selected)
            self.assertEqual(fake.resources[subject.collection + "/teams-first"]["properties"]["state"], "Disabled")
            fake.resources[subject.collection + "/teams-first"]["properties"]["metadata"]["functionAppName"] = "foreign"
            previous = len(fake.writes)
            with self.assertRaisesRegex(ValueError, "unowned"):
                subject.configure(selected)
            self.assertEqual(len(fake.writes), previous)

    def test_webhook_selection_registers_callbacks_and_disables_skipped_listeners(self):
        with tempfile.TemporaryDirectory() as directory:
            subject, fake = self.create(directory, "webhook")
            selected = [{"functionName": "First", "operationName": "Subscribe", "parameters": [{"name": "body", "value": {"id": "chat"}}]}]
            subject.configure(selected)
            self.assertEqual(len(fake.writes), 1)
            callback = fake.writes[0]["properties"]["notificationDetails"]
            self.assertEqual(callback["callbackUrl"], "https://app.azurewebsites.net/runtime/webhooks/connector?functionName=First")
            self.assertEqual(callback["authentication"]["value"], "private-key")
            self.assertEqual(fake.settings, {"AzureWebJobs.First.Disabled": "false", "AzureWebJobs.Second.Disabled": "true"})
            self.assertNotIn("private-key", fake.outputs["WEBHOOK_TRIGGER_INPUTS"])

    def test_json_inputs_skip_interaction_and_existing_local_settings_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            subject, _ = self.create(directory)
            selected = [{"functionName": "First", "operationName": "Subscribe", "parameters": []}]
            (subject.project / "trigger-inputs.json").write_text(json.dumps(selected))
            subject.prompt = lambda _: self.fail("Explicit inputs must not prompt")
            self.assertEqual(subject.select(), selected)
            path = subject.project / "local.settings.json"
            path.write_bytes(b"existing bytes\n")
            subject.write_local({"new": "value"})
            self.assertEqual(path.read_bytes(), b"existing bytes\n")

    def test_onedrive_explicit_inputs_reject_literal_root_before_source_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            subject, fake = self.create(directory)
            subject.config["connectorName"] = "onedriveforbusiness"
            for folder in ("root", "NULL", "/Documents", ""):
                with self.subTest(folder=folder), self.assertRaisesRegex(ValueError, "connector-returned"):
                    subject.configure([{"functionName": "First", "operationName": "Subscribe",
                                        "parameters": [{"name": "folderId", "value": folder}]}])
            self.assertEqual(fake.writes, [])

    def test_planner_deployment_uses_authenticated_group_and_plan_pickers_in_both_modes(self):
        swagger = {"paths": {
            "/subscribe": {"get": {"operationId": "OnCompleteTask_V3", "parameters": [
                {"name": "groupId", "in": "query", "type": "string", "required": True,
                 "x-ms-dynamic-values": picker("Groups")},
                {"name": "id", "in": "query", "type": "string", "required": True,
                 "x-ms-dynamic-values": picker("Plans", {"group": {"parameter": "groupId"}})},
            ]}},
            "/groups": {"get": {"operationId": "Groups", "parameters": []}},
            "/plans/{group}": {"get": {"operationId": "Plans", "parameters": [
                {"name": "group", "in": "path", "required": True},
            ]}},
        }}

        class Connector:
            outputs = {"AZURE_SUBSCRIPTION_ID": "sub", "connectorNamespaceConnectionName": "connection"}
            collection = "https://management.azure.com/namespace/triggerConfigs"
            authorized = False

            def authorize(self):
                self.authorized = True

            def rest(self, *_args):
                if not self.authorized:
                    raise AssertionError("Picker metadata requested before authorization")
                return swagger

            def az(self, *arguments):
                request = json.loads(Path(arguments[arguments.index("--body") + 1][1:]).read_text())["request"]
                identifier = "group-id-real" if request["path"] == "/groups" else "plan-id-real"
                return {"response": {"statusCode": 200, "body": {"items": [{"id": identifier, "name": identifier}]}}}

        for mode in ("polling",):
            project = ROOT / "plannerApp" / mode
            with self.subTest(mode=mode), patch.dict(sys.modules, {"trigger_inputs": inputs}):
                planner = load(mode + "_planner_setup", project / "infra/scripts/setup.py")
                answers = iter(("2", "1", "1", "1", "1"))
                with tempfile.TemporaryDirectory() as directory:
                    isolated = Path(directory)
                    (isolated / "infra").mkdir()
                    shutil.copyfile(project / "infra/triggers.json", isolated / "infra/triggers.json")
                    with patch.dict(os.environ, {key: "" for key in ("PLANNER_TRIGGER_INPUTS", "PLANNER_GROUP_ID", "PLANNER_PLAN_ID")}):
                        selected = planner.select_inputs(isolated, prompt=lambda _: next(answers), connector_setup=Connector())
                self.assertEqual(selected, [{"functionName": "OnPlannerCompleteTask", "operationName": "OnCompleteTask_V3",
                                             "parameters": [{"name": "groupId", "value": "group-id-real"},
                                                            {"name": "id", "value": "plan-id-real"}]}])

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is required for Dataverse journal tests")
    def test_dataverse_action_body_keeps_polling_cleanup_journal_guard(self):
        for mode in ("polling",):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / mode
                scripts = project / "infra/scripts"
                scripts.mkdir(parents=True)
                for name in ("guard-action.ps1", "deployment-helpers.ps1", "action-cleanup.ps1", "local-settings.ps1"):
                    shutil.copyfile(ROOT / f"dataverseApp/{mode}/infra/scripts" / name, scripts / name)
                parameters = [
                    {"name": "organization", "value": "https://test.crm.dynamics.com"},
                    {"name": "catalog", "value": "catalog"}, {"name": "category", "value": "category"},
                    {"name": "body", "value": {"entityname": "account", "sdkmessagename": "action", "scope": 4, "version": 3}},
                ]
                outputs = {"AZURE_SUBSCRIPTION_ID": "sub", "resourceGroupName": "rg", "connectorNamespaceName": "namespace",
                           "connectorNamespaceConnectionName": "connection", "functionAppName": "app",
                           "functionAppDefaultHostname": "app.azurewebsites.net", "dataverseEnvironmentUrl": "https://test.crm.dynamics.com"}
                request = {"outputs": outputs, "parameters": parameters, "resource": None, "mode": "Poll" if mode == "polling" else "Webhook"}
                path = Path(directory) / "request.json"
                path.write_text(json.dumps(request))
                command = ["pwsh", "-NoProfile", "-File", str(scripts / "guard-action.ps1"), str(path)]
                first = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(first.returncode, 0, first.stderr)
                journals = list((project / ".azure").glob("dataverse-action-cleanup-*.json"))
                self.assertEqual(len(journals), 1)
                journal = json.loads(journals[0].read_text())
                self.assertEqual(journal["selectors"]["sdkmessagename"], "action")
                retry = subprocess.run(command, capture_output=True, text=True)
                self.assertNotEqual(retry.returncode, 0, "A missing CN config must not silently replace an unverified source subscription")


if __name__ == "__main__":
    unittest.main()
