# Copyright (c) Microsoft Corporation.  All rights reserved.
"""Index Salesforce functions and decode records with the installed Functions SDK."""

import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import List

SAMPLE = Path(__file__).resolve().parents[1]


class RuntimeBindingTests(unittest.TestCase):
    """Use actual SDK indexing and converters, without starting a cloud host."""

    def test_both_modes_index_list_bindings_and_decode_record_batches(self):
        try:
            from azurefunctions.extensions.base import Datum
            from azurefunctions.extensions.connectors.salesforce import ConnectorConverter, Item
        except ImportError as error:
            self.skipTest(f"Install the sample runtime dependencies first: {error}")
        records = [{"Id": "record-1", "Optional__c": None}, {"Id": "record-2", "Enabled__c": False}]
        for mode in ("polling", "webhook"):
            specification = importlib.util.spec_from_file_location("salesforce_runtime_" + mode, SAMPLE / mode / "function_app.py")
            module = importlib.util.module_from_spec(specification)
            specification.loader.exec_module(module)
            functions = module.app.get_functions()
            self.assertEqual(len(functions), 2)
            for function in functions:
                handler = function.get_user_function()
                annotation = handler.__annotations__["records"]
                self.assertEqual(annotation, List[Item])
                self.assertTrue(ConnectorConverter.check_input_type_annotation(annotation))
                binding = next(item for item in json.loads(function.get_function_json())["bindings"] if item["type"] == "connectorTrigger")
                self.assertEqual(binding["name"], "records")
                self.assertEqual(binding["direction"].lower(), "in")
                self.assertEqual(binding["connection"], "ConnectorNamespace")
                if mode == "polling":
                    self.assertEqual(binding["deliveryMode"], "Poll")
                    self.assertEqual(binding["triggerConfigName"], "%" + function.get_function_name() + "TriggerConfigName%")
                else:
                    self.assertNotIn("deliveryMode", binding)
                    self.assertNotIn("triggerConfigName", binding)
                cases = [
                    (Datum(type="json", value={"body": {"value": records}, "headers": {}, "statusCode": 200}), records),
                    (Datum(type="json", value={"body": {"value": []}}), []),
                    (Datum(type="collection_string", value=SimpleNamespace(string=[json.dumps({"body": record}) for record in records])), records),
                ]
                for data, expected in cases:
                    with self.subTest(mode=mode, function=function.get_function_name(), kind=data.type, size=len(expected)):
                        converted = ConnectorConverter.decode(data=data, trigger_metadata=None, pytype=annotation)
                        self.assertEqual([item.dynamic_properties for item in converted], expected)
                        with self.assertLogs(level="INFO") as logs:
                            handler(converted)
                        self.assertEqual(logs.output, [f"INFO:root:{function.get_function_name()}: {len(expected)} records"])


if __name__ == "__main__":
    unittest.main()