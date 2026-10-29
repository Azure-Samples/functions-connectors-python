# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Offline contracts for the registered samples using real connector bindings.

Run with ``python -m unittest discover -s tests -v`` in an environment with the
sample requirements installed (or the approved editable binding/SDK checkouts).
No Functions host, credentials, or Azure resources are needed.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import re
import sys
import unittest
from collections import Counter
from functools import lru_cache
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import get_args, get_origin, get_type_hints
from unittest.mock import AsyncMock, MagicMock, patch

import azure.functions as func
from azure.connectors import ConnectorException
from azure.core.async_paging import AsyncItemPaged
from azurefunctions.extensions.base import Datum
from azurefunctions.extensions.connectors.connectorConverter import ConnectorConverter


ROOT = Path(__file__).resolve().parents[1]
DOTNET_PARITY_SHA = "291b916c5518389f3864d1cbd0d9fc722dd98588"

# This is a fixed inventory from the .NET reference revision above, not a list
# derived from the Python implementation. Kusto is an explicit Python addition.
DOTNET_FUNCTIONS = {
    "azureblobApp": {"OnAzureBlobUpdatedFile"},
    "dataverseApp": {"OnDataverseRowChanged", "ListDataverseRows"},
    "office365App": {
        "OnNewEmail", "OnFlaggedEmail", "OnNewMentionMeEmail",
        "OnNewCalendarEvent", "OnUpcomingEvent",
    },
    "onedriveApp": {"OnOneDriveNewFile", "OnOneDriveUpdatedFile"},
    "sharepointApp": {"OnSharepointNewFile", "OnSharepointUpdatedFile"},
    "teamsApp": {
        "OnNewChannelMessage", "OnNewChannelMessageMentioningMe",
        "OnGroupMembershipAdd", "OnGroupMembershipRemoval",
    },
    "genericApp": {
        "OnGenericAzureBlobUpdated", "OnGenericCustomConnectorEvent",
        "OnGenericOffice365NewEmail", "OnGenericSharepointNewFile",
        "OnGenericTeamsChannelMessage",
    },
}
PYTHON_ONLY_FUNCTIONS = {"kustoApp": {"OnKustoQueryResult"}}
FUNCTIONS = {**DOTNET_FUNCTIONS, **PYTHON_ONLY_FUNCTIONS}

TRIGGER_OPERATIONS = {
    "azureblobApp": {"OnAzureBlobUpdatedFile": "OnUpdatedFiles_V2"},
    "dataverseApp": {"OnDataverseRowChanged": "GetOnNewItems_V2"},
    "office365App": {
        "OnNewEmail": "OnNewEmailV3",
        "OnFlaggedEmail": "OnFlaggedEmailV4",
        "OnNewMentionMeEmail": "OnNewMentionMeEmailV3",
        "OnNewCalendarEvent": "CalendarGetOnNewItemsV3",
        "OnUpcomingEvent": "OnUpcomingEventsV3",
    },
    "onedriveApp": {
        "OnOneDriveNewFile": "OnNewFilesV2",
        "OnOneDriveUpdatedFile": "OnUpdatedFilesV2",
    },
    "sharepointApp": {
        "OnSharepointNewFile": "GetOnNewFileItems",
        "OnSharepointUpdatedFile": "GetOnUpdatedFileItems",
    },
    "teamsApp": {
        "OnNewChannelMessage": "OnNewChannelMessage",
        "OnNewChannelMessageMentioningMe": "OnNewChannelMessageMentioningMe",
        "OnGroupMembershipAdd": "OnGroupMembershipAdd",
        "OnGroupMembershipRemoval": "OnGroupMembershipRemoval",
    },
}

# Each entry pins the extension annotation separately from the returned SDK type.
TYPED_TRIGGERS = (
    ("office365App", "OnNewEmail", "office365", "GraphClientReceiveMessage", "email"),
    ("office365App", "OnFlaggedEmail", "office365", "GraphClientReceiveMessage", "email"),
    ("office365App", "OnNewMentionMeEmail", "office365", "GraphClientReceiveMessage", "email"),
    ("office365App", "OnNewCalendarEvent", "office365", "GraphCalendarEventClientReceive", "calendar"),
    ("office365App", "OnUpcomingEvent", "office365", "GraphCalendarEventClientReceive", "calendar"),
    ("onedriveApp", "OnOneDriveNewFile", "onedriveforbusiness", "BlobMetadata", "file"),
    ("onedriveApp", "OnOneDriveUpdatedFile", "onedriveforbusiness", "BlobMetadata", "file"),
    ("sharepointApp", "OnSharepointNewFile", "sharepointonline", "Item", "sharepoint"),
    ("sharepointApp", "OnSharepointUpdatedFile", "sharepointonline", "Item", "sharepoint"),
    ("teamsApp", "OnNewChannelMessage", "teams", "ChatMessage", "message"),
    ("teamsApp", "OnNewChannelMessageMentioningMe", "teams", "ChatMessage", "message"),
    ("teamsApp", "OnGroupMembershipAdd", "teams", "OnGroupMemberChangeResponse", "member"),
    ("teamsApp", "OnGroupMembershipRemoval", "teams", "OnGroupMemberChangeResponse", "member"),
    ("dataverseApp", "OnDataverseRowChanged", "commondataservice", "Item", "row"),
)


@lru_cache(maxsize=None)
def load_app(app_name: str) -> tuple[ModuleType, dict]:
    """Import and index each real FunctionApp once under its own module name."""
    module_name = f"_offline_connector_sample_{app_name}"
    spec = importlib.util.spec_from_file_location(
        module_name, ROOT / app_name / "function_app.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load sample '{app_name}'.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        with patch.dict(os.environ, {
            "DATAVERSE_TABLE_NAME": "accounts",
            "DATAVERSE_ENVIRONMENT_URL": "https://sample.crm.test",
        }):
            spec.loader.exec_module(module)
        registered = module.app.get_functions()
        functions = {item.get_function_name(): item for item in registered}
        if len(functions) != len(registered):
            raise AssertionError(f"Duplicate registered names in '{app_name}'.")
        return module, functions
    except Exception:
        sys.modules.pop(module_name, None)
        raise


def registered_handler(app_name: str, function_name: str) -> tuple:
    """Read the user function and its annotation from the indexed registration."""
    _, functions = load_app(app_name)
    registered = functions[function_name]
    handler = registered.get_user_function()
    argument = registered.get_trigger().get_dict_repr()["name"]
    return handler, argument, get_type_hints(handler)[argument]


def callback_shapes(payload: object):
    """Use actual Datum transport shapes, including Poll MANY's string field."""
    yield "json-object", Datum(value=payload, type="json")
    yield "json-text", Datum(value=json.dumps(payload), type="json")
    yield "string", Datum(value=json.dumps(payload), type="string")
    yield "collection_string", Datum(
        value=SimpleNamespace(string=[json.dumps(payload)]),
        type="collection_string",
    )


def record_fixture(family: str, ordinal: int = 1) -> dict:
    """Build distinct wire records so batch order and dropped fields are visible."""
    return {
        "email": {
            "id": f"email-{ordinal}", "subject": f"Mail {ordinal}",
            "from": f"sender{ordinal}@example.test", "importance": "high",
            "hasAttachments": False,
        },
        "calendar": {
            "id": f"event-{ordinal}", "subject": f"Meeting {ordinal}",
            "organizer": f"organizer{ordinal}@example.test",
            "start": f"2026-10-29T0{ordinal}:00:00",
            "end": f"2026-10-29T0{ordinal}:30:00",
        },
        "file": {
            "Id": f"file-{ordinal}", "Name": f"report-{ordinal}.txt",
            "Path": f"/reports/report-{ordinal}.txt", "Size": ordinal * 10,
            "LastModified": "2026-10-29T10:00:00Z",
        },
        "sharepoint": {
            "{FilenameWithExtension}": f"report-{ordinal}.txt",
            "{Path}": "/Shared Documents/", "ID": ordinal,
            "Modified": "2026-10-29T10:00:00Z", "CustomColumn": False,
        },
        "message": {
            "id": f"message-{ordinal}",
            "from": {"user": {"displayName": f"Sender {ordinal}"}},
            "body": {"content": f"Hello {ordinal}", "contentType": "text"},
        },
        "member": {
            "id": f"member-{ordinal}", "displayName": f"Member {ordinal}",
            "roles": ["member"], "enabled": False, "optional": None,
        },
        "row": {
            "ItemInternalId": f"internal-{ordinal}",
            "accountid": f"account-{ordinal}", "name": f"Account {ordinal}",
            "active": False, "optional": None,
        },
    }[family]


def expected_logs(function_name: str, family: str, records: list[dict]) -> list[str]:
    """Pin every emitted field and batch count, not just the trigger banner."""
    messages = [f"{function_name} trigger received."]
    if family == "row":
        messages.append("Environment: 'https://sample.crm.test', Table: 'accounts'.")
    for record in records:
        if family == "email":
            messages.extend([
                f"Subject: '{record['subject']}'.", f"From: '{record['from']}'.",
            ])
            if function_name != "OnNewMentionMeEmail":
                messages.append(f"Importance: '{record['importance']}'.")
            if function_name == "OnNewEmail":
                messages.append(f"Has attachments: '{record['hasAttachments']}'.")
        elif family == "calendar":
            messages.append(f"Subject: '{record['subject']}'.")
            if function_name == "OnNewCalendarEvent":
                messages.append(f"Organizer: '{record['organizer']}'.")
            messages.append(f"Start: '{record['start']}'.")
            if function_name == "OnNewCalendarEvent":
                messages.append(f"End: '{record['end']}'.")
        elif family in ("file", "sharepoint"):
            name_key = "Name" if family == "file" else "{FilenameWithExtension}"
            path_key = "Path" if family == "file" else "{Path}"
            messages.extend([
                f"Name: '{record[name_key]}'.", f"Path: '{record[path_key]}'.",
            ])
            if function_name == "OnOneDriveNewFile":
                messages.append(f"Size: '{record['Size']}'.")
            elif function_name == "OnSharepointNewFile":
                messages.append(f"Item ID: '{record['ID']}'.")
            else:
                modified_key = "LastModified" if family == "file" else "Modified"
                messages.append(f"LastModified: '{record[modified_key]}'.")
        elif family == "message":
            sender = (record.get("from") or {}).get("user") or {}
            body = record.get("body") or {}
            messages.extend([
                f"Id: '{record['id']}'.", f"From: '{sender.get('displayName')}'.",
                f"Content: '{body.get('content')}'.",
            ])
        elif family == "member":
            messages.append(f"Member: '{json.dumps(record)}'.")
        elif family == "row":
            record_id = record.get("ItemInternalId") or record.get("accountid") or "<unset>"
            messages.extend([
                f"New 'accounts' row id: '{record_id}'.",
                f"Columns in payload: {list(record.keys())}.",
            ])
    batch_units = {
        "OnNewEmail": "email(s)", "OnNewCalendarEvent": "event(s)",
        "OnDataverseRowChanged": "new row(s)",
    }
    if function_name in batch_units:
        messages.append(f"Batch contains '{len(records)}' {batch_units[function_name]}.")
    return messages


class SampleBindingTests(unittest.TestCase):
    """Exercise the complete converter-to-handler path for all 14 typed triggers."""

    def assert_decoded_callback(self, case: tuple, data: Datum, records: list[dict]) -> None:
        """Check real SDK model values and then invoke the registered user code."""
        app_name, function_name, connector, model_name, family = case
        handler, argument, annotation = registered_handler(app_name, function_name)
        decoded = ConnectorConverter.decode(
            data=data, trigger_metadata=None, pytype=annotation,
        )
        self.assertIs(type(decoded), list)
        self.assertEqual(len(decoded), len(records))
        model = getattr(importlib.import_module(f"azure.connectors.{connector}"), model_name)
        for item, record in zip(decoded, records):
            if family == "member":
                self.assertIs(type(item), dict)
                self.assertEqual(item, record)
            else:
                self.assertIs(type(item), model)
                if family in ("sharepoint", "row"):
                    self.assertEqual(item.dynamic_properties, record)
                else:
                    fields = {
                        "email": {"id": "id", "subject": "subject", "from_": "from",
                                  "importance": "importance", "has_attachments": "hasAttachments"},
                        "calendar": {"id": "id", "subject": "subject", "organizer": "organizer",
                                     "start": "start", "end": "end"},
                        "file": {"id": "Id", "name": "Name", "path": "Path", "size": "Size",
                                 "last_modified": "LastModified"},
                        "message": {"id": "id", "from_": "from", "body": "body"},
                    }[family]
                    for attribute, wire_name in fields.items():
                        self.assertEqual(getattr(item, attribute), record[wire_name])
                    if family == "message":
                        for attribute in ("body", "from_"):
                            if getattr(item, attribute) is not None:
                                self.assertIs(type(getattr(item, attribute)), dict)
        with self.assertLogs(level="INFO") as captured:
            self.assertIsNone(handler(**{argument: decoded}))
        self.assertEqual(
            [entry.getMessage() for entry in captured.records],
            expected_logs(function_name, family, records),
        )

    def test_registered_annotations_are_actual_extension_lists(self) -> None:
        self.assertEqual(len(TYPED_TRIGGERS), 14)
        self.assertEqual(len({case[:2] for case in TYPED_TRIGGERS}), 14)
        for app_name, function_name, connector, model_name, _ in TYPED_TRIGGERS:
            with self.subTest(app=app_name, function=function_name):
                _, _, annotation = registered_handler(app_name, function_name)
                extension = importlib.import_module(
                    f"azurefunctions.extensions.connectors.{connector}",
                )
                self.assertIs(get_origin(annotation), list)
                self.assertEqual(get_args(annotation), (getattr(extension, model_name),))
                self.assertTrue(ConnectorConverter.check_input_type_annotation(annotation))

    def test_populated_callbacks_decode_and_execute_all_typed_handlers(self) -> None:
        for case in TYPED_TRIGGERS:
            records = [record_fixture(case[4], ordinal) for ordinal in (1, 2)]
            payloads = {
                "direct": records[0],
                "wrapped-record": {"body": records[0]},
                "batch": {"value": records},
                "wrapped-batch": {"body": {"@odata.context": "sample", "value": records}},
            }
            for envelope, payload in payloads.items():
                for transport, data in callback_shapes(payload):
                    with self.subTest(function=case[1], envelope=envelope, transport=transport):
                        expected = records[:1] if envelope in ("direct", "wrapped-record") else records
                        self.assert_decoded_callback(case, data, expected)

    def test_empty_and_null_callbacks_execute_all_typed_handlers(self) -> None:
        for case in TYPED_TRIGGERS:
            for payload in ({"body": None}, {"value": []}, {"value": None},
                            {"body": {"value": []}}, {"body": {"value": None}}):
                for transport, data in callback_shapes(payload):
                    with self.subTest(function=case[1], payload=payload, transport=transport):
                        self.assert_decoded_callback(case, data, [])
            with self.subTest(function=case[1], transport="empty-collection_string"):
                self.assert_decoded_callback(case, Datum(
                    value=SimpleNamespace(string=[]), type="collection_string",
                ), [])

    def test_poll_many_flattens_distinct_events_in_order(self) -> None:
        for case in TYPED_TRIGGERS:
            records = [record_fixture(case[4], ordinal) for ordinal in (1, 2, 3)]
            with self.subTest(function=case[1]):
                self.assert_decoded_callback(case, Datum(
                    value=SimpleNamespace(string=[
                        json.dumps({"body": records[0]}),
                        json.dumps({"body": {"value": []}}),
                        json.dumps({"body": {"value": records[1:]}}),
                    ]), type="collection_string",
                ), records)

    def test_invalid_callbacks_raise_for_every_typed_annotation(self) -> None:
        invalid_payloads = (
            None, "not-json", 7, False, {"body": "invalid"},
        )
        for case in TYPED_TRIGGERS:
            # The existing Office 365 wrappers intentionally retain permissive
            # batch-member parsing; test strict members on the newer bindings.
            payloads = invalid_payloads if case[2] == "office365" else invalid_payloads + (
                {"value": [None]}, {"value": [False]}, {"value": ["invalid"]},
                {"body": {"value": [{"id": "valid-first"}, None]}},
            )
            for payload in payloads:
                for transport, data in callback_shapes(payload):
                    with self.subTest(function=case[1], payload=payload, transport=transport):
                        _, _, annotation = registered_handler(case[0], case[1])
                        with self.assertRaises(ValueError):
                            ConnectorConverter.decode(
                                data=data, trigger_metadata=None, pytype=annotation,
                            )
            for transport in ("string", "json", "collection_string"):
                with self.subTest(function=case[1], transport=transport, malformed_json=True):
                    value = SimpleNamespace(string=["{"]) if transport == "collection_string" else "{"
                    _, _, annotation = registered_handler(case[0], case[1])
                    with self.assertRaises(ValueError):
                        ConnectorConverter.decode(
                            data=Datum(value=value, type=transport),
                            trigger_metadata=None, pytype=annotation,
                        )

    def test_teams_null_sender_and_body_remain_valid_sdk_messages(self) -> None:
        for case in TYPED_TRIGGERS:
            if case[4] != "message":
                continue
            for sender in (None, {}, {"user": None}, {"user": {}}):
                for body in (None, {}):
                    record = {"id": "message-null", "from": sender, "body": body}
                    for transport, data in callback_shapes({"body": {"value": [record]}}):
                        with self.subTest(function=case[1], sender=sender, body=body, transport=transport):
                            self.assert_decoded_callback(case, data, [record])

    def test_dataverse_record_id_precedence_and_fallback(self) -> None:
        case = next(case for case in TYPED_TRIGGERS if case[4] == "row")
        for record in ({"ItemInternalId": "internal", "accountid": "primary"},
                       {"accountid": "primary"}, {"ItemInternalId": "", "accountid": "primary"},
                       {"name": "No primary key"}):
            for transport, data in callback_shapes({"body": {"value": [record]}}):
                with self.subTest(record=record, transport=transport):
                    self.assert_decoded_callback(case, data, [record])


class DataverseActionTests(unittest.IsolatedAsyncioTestCase):
    """Exercise the registered action with real paging and fake resource contexts."""

    async def asyncSetUp(self) -> None:
        self.module, functions = load_app("dataverseApp")
        self.handler = functions["ListDataverseRows"].get_user_function()

    async def invoke_pages(
        self, pages: list[tuple[str | None, list[dict]]], *,
        params: dict[str, str] | None = None, in_azure: bool = False,
        expected_table: str = "accounts", expected_top: int = 5,
        error: ConnectorException | None = None,
    ) -> tuple[func.HttpResponse, list[str | None]]:
        """Verify lazy page fetches and item reads stay inside both resource contexts."""
        credential = MagicMock()
        client = MagicMock()
        opened = set()
        events = []
        fetched = []
        extracted = []

        async def enter_credential():
            self.assertEqual(opened, set())
            opened.add("credential")
            events.append("credential-enter")
            return credential

        async def exit_credential(*arguments):
            self.assertEqual(opened, {"credential"})
            opened.remove("credential")
            events.append("credential-exit")

        async def enter_client():
            self.assertEqual(opened, {"credential"})
            opened.add("client")
            events.append("client-enter")
            return client

        async def exit_client(*arguments):
            self.assertEqual(opened, {"credential", "client"})
            opened.remove("client")
            events.append("client-exit")

        credential.__aenter__ = AsyncMock(side_effect=enter_credential)
        credential.__aexit__ = AsyncMock(side_effect=exit_credential)
        client.__aenter__ = AsyncMock(side_effect=enter_client)
        client.__aexit__ = AsyncMock(side_effect=exit_client)

        async def get_next(continuation_token):
            self.assertEqual(opened, {"credential", "client"})
            expected_token = None if not fetched else pages[len(fetched) - 1][0]
            self.assertEqual(continuation_token, expected_token)
            fetched.append(continuation_token)
            if error is not None and len(fetched) > len(pages):
                raise error
            self.assertLessEqual(len(fetched), len(pages), "Fetched past the last page.")
            return pages[len(fetched) - 1]

        async def extract_data(page):
            self.assertEqual(opened, {"credential", "client"})
            extracted.append(page)

            async def items():
                for row in page[1]:
                    self.assertEqual(opened, {"credential", "client"})
                    yield row

            return page[0], items()

        def list_items(**arguments):
            self.assertEqual(opened, {"credential", "client"})
            self.assertEqual(arguments, {
                "dataset": "https://sample.crm.test", "table": expected_table,
                "top": expected_top,
            })
            self.assertIs(type(arguments["top"]), int)
            return AsyncItemPaged(get_next=get_next, extract_data=extract_data)

        client.list_items.side_effect = list_items
        with patch.multiple(
            self.module, RUNTIME_URL="https://connection.example.test/runtime",
            DATAVERSE_DATASET="https://sample.crm.test", DATAVERSE_TABLE="accounts",
            IN_AZURE=in_azure,
        ), patch.object(self.module, "CommondataserviceClient", return_value=client) as factory, \
                patch.object(self.module, "AzureCliCredential", return_value=credential) as cli, \
                patch.object(self.module, "ManagedIdentityCredential", return_value=credential) as managed:
            response = await self.handler(func.HttpRequest(
                method="GET", url="https://sample.example.test/api/rows",
                params=params or {}, body=b"",
            ))
            factory.assert_called_once_with(
                "https://connection.example.test/runtime", credential=credential,
            )
            (managed if in_azure else cli).assert_called_once_with()
            (cli if in_azure else managed).assert_not_called()

        client.list_items.assert_called_once()
        self.assertEqual(extracted, pages)
        self.assertEqual(len(fetched), len(pages) + (error is not None))
        self.assertEqual(opened, set())
        self.assertEqual(events, [
            "credential-enter", "client-enter", "client-exit", "credential-exit",
        ])
        for resource in (credential, client):
            resource.__aenter__.assert_awaited_once_with()
            resource.__aexit__.assert_awaited_once()
        self.assertEqual(response.mimetype, "application/json")
        return response, fetched

    async def test_empty_pager_returns_empty_rows(self) -> None:
        response, fetched = await self.invoke_pages([(None, [])])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), {
            "table": "accounts", "count": 0, "value": [],
        })
        self.assertEqual(fetched, [None])

    async def test_populated_pager_fetches_all_continuations_in_order(self) -> None:
        rows = [record_fixture("row", ordinal) for ordinal in (1, 2, 3)]
        response, fetched = await self.invoke_pages([
            ("page-2", rows[:1]), ("page-3", rows[1:2]), (None, rows[2:]),
        ])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), {
            "table": "accounts", "count": 3, "value": rows,
        })
        self.assertEqual(fetched, [None, "page-2", "page-3"])

    async def test_empty_first_page_still_fetches_continuation(self) -> None:
        rows = [record_fixture("row")]
        response, fetched = await self.invoke_pages([("next-page", []), (None, rows)])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.get_body()), {
            "table": "accounts", "count": 1, "value": rows,
        })
        self.assertEqual(fetched, [None, "next-page"])

    async def test_table_and_integer_top_overrides_for_both_credentials(self) -> None:
        for in_azure in (False, True):
            for params, table, top in (
                ({"table": "contacts", "top": "12"}, "contacts", 12),
                ({"table": "leads"}, "leads", 5),
                ({"table": "", "top": "1"}, "accounts", 1),
            ):
                with self.subTest(in_azure=in_azure, params=params):
                    rows = [{"contactid": "contact-1", "enabled": False}]
                    response, _ = await self.invoke_pages(
                        [(None, rows)], params=params, in_azure=in_azure,
                        expected_table=table, expected_top=top,
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(json.loads(response.get_body()), {
                        "table": table, "count": 1, "value": rows,
                    })

    async def test_invalid_top_returns_400_without_opening_resources(self) -> None:
        for top in ("", "0", "-1", "1.5", "abc", "true"):
            with self.subTest(top=top), patch.multiple(
                self.module, RUNTIME_URL="https://connection.example.test/runtime",
                DATAVERSE_DATASET="https://sample.crm.test",
            ), patch.object(self.module, "CommondataserviceClient") as client, \
                    patch.object(self.module, "AzureCliCredential") as cli, \
                    patch.object(self.module, "ManagedIdentityCredential") as managed:
                response = await self.handler(func.HttpRequest(
                    method="GET", url="https://sample.example.test/api/rows",
                    params={"top": top}, body=b"",
                ))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_body().decode(),
                                 "Parameter 'top' must be a positive integer.")
                for factory in (client, cli, managed):
                    factory.assert_not_called()

    async def test_missing_configuration_returns_500_without_opening_resources(self) -> None:
        for runtime, dataset, setting in (
            (None, "https://sample.crm.test", "COMMONDATASERVICE_CONNECTION_RUNTIME_URL"),
            ("", "https://sample.crm.test", "COMMONDATASERVICE_CONNECTION_RUNTIME_URL"),
            ("https://connection.example.test/runtime", "", "DATAVERSE_ENVIRONMENT_URL"),
        ):
            with self.subTest(setting=setting, runtime=runtime), patch.multiple(
                self.module, RUNTIME_URL=runtime, DATAVERSE_DATASET=dataset,
            ), patch.object(self.module, "CommondataserviceClient") as client, \
                    patch.object(self.module, "AzureCliCredential") as cli, \
                    patch.object(self.module, "ManagedIdentityCredential") as managed:
                response = await self.handler(func.HttpRequest(
                    method="GET", url="https://sample.example.test/api/rows", body=b"",
                ))
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.get_body().decode(), f"{setting} is not configured.")
                for factory in (client, cli, managed):
                    factory.assert_not_called()

    async def test_connector_exception_preserves_status_and_full_body(self) -> None:
        for status in (403, 429, 502):
            for during_continuation in (False, True):
                with self.subTest(status=status, during_continuation=during_continuation):
                    body = json.dumps({"error": {"code": "ConnectorFailure", "message": "!" * 2100}})
                    error = ConnectorException(
                        method="GET", path="/datasets/sample/tables/accounts/items",
                        status_code=status, response_body=body,
                    )
                    pages = [("failing-page", [record_fixture("row")])] if during_continuation else []
                    with self.assertLogs(level="ERROR"):
                        response, fetched = await self.invoke_pages(pages, error=error)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.get_body().decode(), body)
                    self.assertEqual(fetched, [None, "failing-page"] if pages else [None])


class SampleInventoryTests(unittest.TestCase):
    """Keep function names, dependency floors, and script registrations aligned."""

    def test_all_eight_apps_match_pinned_parity_inventory(self) -> None:
        self.assertEqual(DOTNET_PARITY_SHA, "291b916c5518389f3864d1cbd0d9fc722dd98588")
        self.assertEqual(
            {path.parent.name for path in ROOT.glob("*App/function_app.py")}, set(FUNCTIONS),
        )
        module_names = set()
        for app_name, expected in FUNCTIONS.items():
            with self.subTest(app=app_name, reference=DOTNET_PARITY_SHA):
                module, functions = load_app(app_name)
                self.assertNotIn(module.__name__, module_names)
                module_names.add(module.__name__)
                self.assertEqual(set(functions), expected)
                for name, function in functions.items():
                    trigger = function.get_trigger().get_dict_repr()
                    self.assertEqual(
                        trigger["type"], "httpTrigger" if name == "ListDataverseRows" else "connectorTrigger",
                    )
                    if name == "ListDataverseRows":
                        self.assertEqual(trigger["route"], "rows")
                        self.assertEqual([
                            (method.value if isinstance(method, func.HttpMethod) else str(method)).upper()
                            for method in trigger["methods"]
                        ], ["GET"])

    def test_typed_inventory_covers_every_non_string_connector_trigger(self) -> None:
        expected = {case[:2] for case in TYPED_TRIGGERS}
        for app_name in FUNCTIONS:
            with self.subTest(app=app_name):
                _, functions = load_app(app_name)
                actual = set()
                for name, function in functions.items():
                    if function.get_trigger().get_dict_repr()["type"] != "connectorTrigger":
                        continue
                    _, _, annotation = registered_handler(app_name, name)
                    if annotation is not str:
                        actual.add((app_name, name))
                self.assertEqual(actual, {pair for pair in expected if pair[0] == app_name})

    def test_all_apps_require_approved_preview_dependency_floors(self) -> None:
        floors = {"azure-functions": (2, 3, 0, 1, 1),
                  "azurefunctions-extensions-connectors": (1, 0, 0, 1, 4)}
        for app_name in FUNCTIONS:
            text = (ROOT / app_name / "requirements.txt").read_text(encoding="utf-8")
            app_floors = dict(floors)
            if app_name == "dataverseApp":
                app_floors["azure-connectors"] = (0, 6, 0, 1, 1)
                module, _ = load_app(app_name)
                self.assertFalse(hasattr(module, "AzureIdentityTokenProvider"))
            for package, minimum in app_floors.items():
                with self.subTest(app=app_name, package=package):
                    matches = re.findall(
                        rf"(?m)^\s*{re.escape(package)}\s*>=\s*"
                        r"(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?\s*(?:#.*)?$", text,
                    )
                    self.assertEqual(len(matches), 1, "Expected one explicit minimum version.")
                    major, minor, micro, stage, number = matches[0]
                    version = (int(major), int(minor), int(micro),
                               {"a": 0, "b": 1, "rc": 2, "": 3}[stage], int(number or 0))
                    self.assertGreaterEqual(version, minimum)

    def test_dedicated_powershell_and_shell_operation_function_pairs(self) -> None:
        for app_name, operations in TRIGGER_OPERATIONS.items():
            for suffix in ("ps1", "sh"):
                with self.subTest(app=app_name, script=suffix):
                    text = (ROOT / app_name / "infra" / "scripts" / f"postdeploy.{suffix}").read_text(
                        encoding="utf-8-sig",
                    )
                    if suffix == "ps1":
                        text = text.replace("`\n", " ")
                        pairs = re.findall(
                            r"-FunctionName\s+['\"]([^'\"]+)['\"]\s+"
                            r"-OperationName\s+['\"]([^'\"]+)['\"]", text,
                        )
                        pairs += re.findall(
                            r"\bfunctionName\s*=\s*['\"]([^'\"]+)['\"][;\s]+"
                            r"\$?operationName\s*=\s*['\"]([^'\"]+)['\"]", text, re.IGNORECASE,
                        )
                    else:
                        pairs = re.findall(
                            r"(?m)^create_trigger(?:_config)?\s+\"([^\"]+)\"\s+\"([^\"]+)\"", text,
                        )
                        pairs += re.findall(
                            r'"(On[^"|]+)\|([^"|]+)\|[^"\n]*"', text,
                        )
                        pairs += re.findall(
                            r'(?m)^functionName="([^"]+)"\s+operationName="([^"]+)"', text,
                        )
                    self.assertEqual(Counter(pairs), Counter(operations.items()))


if __name__ == "__main__":
    unittest.main()