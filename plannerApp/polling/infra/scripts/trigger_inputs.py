# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Collect trigger inputs from the authenticated connector's exported metadata."""

import copy
import json
import math
import re
from urllib.parse import quote


def get(value, path):
    if not path:
        return value
    if isinstance(value, dict) and path in value:
        return value[path]
    for key in re.split(r"[/.]", path):
        if not key:
            continue
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and key.isdigit() and int(key) < len(value):
            value = value[int(key)]
        else:
            return None
    return value


def resolve(swagger, schema, visited=frozenset()):
    reference = schema.get("$ref")
    if not reference:
        return schema
    if not reference.startswith("#/") or reference in visited:
        raise ValueError("Unsupported or cyclic connector schema reference.")
    target = swagger
    for key in reference[2:].split("/"):
        target = target[key.replace("~1", "/").replace("~0", "~")]
    return {**resolve(swagger, target, visited | {reference}),
            **{key: value for key, value in schema.items() if key != "$ref"}}


def operation(swagger, operation_id):
    matches = []
    for route, methods in swagger["paths"].items():
        for method, definition in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if definition.get("operationId") == operation_id:
                parameters = {}
                for parameter in methods.get("parameters", []) + definition.get("parameters", []):
                    parameter = resolve(swagger, parameter)
                    parameters[(parameter["in"], parameter["name"])] = parameter
                matches.append((route, method.upper(), list(parameters.values())))
    if len(matches) != 1:
        raise ValueError(f"The connector must expose exactly one {operation_id} operation.")
    return matches[0]


def operation_request(swagger, operation_id, values):
    route, method, parameters = operation(swagger, operation_id)
    request = {"method": method, "path": re.sub(r"^/\{connectionId\}", "", route)}
    for parameter in parameters:
        name, location = parameter["name"], parameter["in"]
        if name == "connectionId":
            continue
        if name not in values:
            if parameter.get("required"):
                raise ValueError(f"{operation_id} requires {name}.")
            continue
        value = values[name]
        if location == "path":
            encoded = quote(str(value), safe="")
            if parameter.get("x-ms-url-encoding") == "double":
                encoded = quote(encoded, safe="")
            request["path"] = request["path"].replace("{" + name + "}", encoded)
        elif location in {"query", "header"}:
            request.setdefault("queries" if location == "query" else "headers", {})[name] = value
        elif location == "body":
            request["body"] = value
        else:
            raise ValueError(f"Unsupported picker parameter location for {operation_id}.")
    if not request["path"].startswith("/") or re.search(r"\{[^}]+\}", request["path"]):
        raise ValueError(f"Invalid picker path for {operation_id}.")
    return request


def make_picker(swagger, request):
    cache = {}

    def invoke(operation_id, values):
        key = json.dumps([operation_id, values], sort_keys=True)
        if key not in cache:
            result = request({"request": operation_request(swagger, operation_id, values)})
            response = result.get("response", {})
            if str(response.get("statusCode")).upper() not in {"200", "201", "OK", "CREATED"}:
                raise ValueError(f"Connector picker {operation_id} failed. Check source permissions.")
            body = response.get("body")
            cache[key] = json.loads(body) if isinstance(body, str) else body
        return cache[key]

    return invoke


def choose_from_terminal(prompt=input):
    def choose(label, choices):
        if not choices:
            raise ValueError(f"No choices returned for {label}.")
        print(f"\n{label}")
        for index, (title, _) in enumerate(choices, 1):
            print(f"  [{index}] {title}")
        while True:
            answer = prompt(f"Enter number (1-{len(choices)}): ").strip()
            if answer.isdigit() and 1 <= int(answer) <= len(choices):
                return choices[int(answer) - 1][1]
    return choose


def prompt_value(label, schema, prompt):
    while True:
        answer = prompt(f"{label}{' (' + schema['description'] + ')' if schema.get('description') else ''}: ").strip()
        kind = schema.get("type")
        if kind == "string":
            if (answer and len(answer) >= schema.get("minLength", 0)
                    and len(answer) <= schema.get("maxLength", math.inf)
                    and ("pattern" not in schema or re.search(schema["pattern"], answer))):
                return answer
        elif kind in {"integer", "number"}:
            try:
                value = int(answer) if kind == "integer" else float(answer)
                if (math.isfinite(value) and schema.get("minimum", -math.inf) <= value
                        <= schema.get("maximum", math.inf)):
                    return value
            except ValueError:
                # Invalid numeric input is expected; fall through to the retry prompt below.
                pass
        else:
            raise ValueError(f"Unsupported input schema for {label}; no values were guessed.")
        print("Enter a non-empty value matching the requested type and constraints.")


def collect_trigger_inputs(swagger, definitions, invoke, *, choose, prompt=input):
    def spec(extension):
        state = extension.get("dynamicState") or {}
        return extension if extension.get("operationId") else {**extension, **state.get("extension", state)}

    def references(schema):
        schema = resolve(swagger, schema)
        result = []
        for name in ("x-ms-dynamic-schema", "x-ms-dynamic-values", "x-ms-dynamic-list"):
            for binding in spec(schema[name]).get("parameters", {}).values() if schema.get(name) else []:
                if isinstance(binding, dict):
                    reference = binding.get("parameter") or binding.get("parameterReference")
                    if reference:
                        result.append(reference)
        for extension in schema.get("x-ms-dynamic-tree", {}).values():
            for binding in extension.get("parameters", {}).values():
                if isinstance(binding, dict):
                    reference = binding.get("parameter") or binding.get("parameterReference")
                    if reference:
                        result.append(reference)
        if schema.get("items"):
            result.extend(references(schema["items"]))
        for child in schema.get("properties", {}).values():
            result.extend(references(child))
        return result

    selected = []
    for definition in definitions:
        function, operation_id = definition["functionName"], definition["operationName"]
        if not choose(f"Configure {function}?", [("Skip", False), ("Configure", True)]):
            continue
        if "parameters" in definition:
            selected.append({key: copy.deepcopy(definition[key])
                             for key in ("functionName", "operationName", "parameters")})
            continue
        parameters = operation(swagger, operation_id)[2]
        body = next((parameter for parameter in parameters if parameter["in"] == "body"), None)
        answers = copy.deepcopy(definition.get("values", {}))

        def lookup(reference):
            if body and reference.split("/")[0].split(".")[0] == body["name"]:
                reference = "body" + reference[len(body["name"]):]
            value = get(answers, reference)
            return get(answers.get("body"), reference) if value is None else value

        def dynamic(extension):
            extension = spec(extension)
            if not extension.get("operationId"):
                raise ValueError("Connector picker metadata has no operation ID.")
            values = {}
            for name, binding in extension.get("parameters", {}).items():
                reference = (binding.get("parameter") or binding.get("parameterReference")) if isinstance(binding, dict) else None
                value = lookup(reference) if reference else binding.get("value", binding) if isinstance(binding, dict) else binding
                if value is None:
                    raise ValueError(f"Select {reference} before resolving {extension['operationId']}.")
                values[name] = value
            return invoke(extension["operationId"], values)

        def fields(properties, required, path):
            parent = answers
            for key in path[:-1]:
                parent = parent.setdefault(key, {})
            if path:
                result = parent.setdefault(path[-1], {})
            else:
                result = answers
            dependencies = {}
            for name, schema in properties.items():
                dependencies[name] = set()
                for reference in references(schema):
                    parts = re.split(r"[/.]", reference)
                    if body and parts[0] == body["name"]:
                        parts[0] = "body"
                    prefix = list(path)
                    if parts[:len(prefix)] == prefix:
                        parts = parts[len(prefix):]
                    if parts and parts[0] in properties and parts[0] != name:
                        dependencies[name].add(parts[0])
            prerequisites = set().union(*dependencies.values()) if dependencies else set()
            remaining = list(properties)
            while remaining:
                name = next((key for key in remaining if not dependencies[key].intersection(remaining)), None)
                if name is None:
                    raise ValueError("Cyclic connector picker dependencies.")
                remaining.remove(name)
                schema = resolve(swagger, properties[name])
                if schema.get("readOnly") or schema.get("x-ms-notification-url"):
                    continue
                if schema.get("x-ms-visibility") == "internal":
                    if "default" in schema:
                        result[name] = copy.deepcopy(schema["default"])
                    continue
                value = collect(schema, schema.get("x-ms-summary") or schema.get("title") or name,
                                [*path, name], name in required or name in prerequisites or schema.get("required") is True)
                if value is not None:
                    result[name] = value
            return result

        def collect(schema, label, path, required=True):
            supplied = get(answers, "/".join(path))
            if supplied is not None and not isinstance(supplied, dict):
                return supplied
            schema = resolve(swagger, schema)
            if supplied is None and not required and not choose(f"Configure {label} (optional)?", [("Skip", False), ("Configure", True)]):
                return None
            if schema.get("x-ms-dynamic-schema"):
                extension = spec(schema["x-ms-dynamic-schema"])
                resolved = get(dynamic(extension), extension.get("value-path") or extension.get("valuePath"))
                if not isinstance(resolved, dict):
                    raise ValueError(f"No schema returned for {label}.")
                schema = {**schema, **resolve(swagger, resolved)}
                del schema["x-ms-dynamic-schema"]
            if schema.get("type") == "array":
                items = []
                item_schema = {**schema["items"], **{key: schema[key] for key in
                               ("x-ms-dynamic-values", "x-ms-dynamic-list") if key in schema}}
                while True:
                    items.append(collect(item_schema, f"{label} ({len(items) + 1})", [*path, str(len(items))]))
                    if len(items) >= schema.get("minItems", 1) and (
                            len(items) >= schema.get("maxItems", math.inf)
                            or not choose(f"Add another {label}?", [("No", False), ("Yes", True)])):
                        return items
            if schema.get("x-ms-dynamic-tree"):
                tree = schema["x-ms-dynamic-tree"]
                stack = []
                while True:
                    current, selector = stack[-1] if stack else (None, tree["open"])
                    extension = copy.deepcopy(tree["browse"] if current else tree["open"])
                    for name, binding in extension.get("parameters", {}).items():
                        if isinstance(binding, dict) and "selectedItemValuePath" in binding:
                            extension["parameters"][name] = {"value": get(current, binding["selectedItemValuePath"])}
                    items = get(dynamic(extension), extension.get("itemsPath"))
                    if not isinstance(items, list):
                        raise ValueError(f"Invalid folder picker response for {label}.")
                    choices = ([("Use this folder", "select"), ("Parent folder", "up")] if current else [])
                    choices.extend((get(item, extension["itemTitlePath"]), item) for item in items
                                   if item.get("IsFolder") is True)
                    if not choices:
                        raise ValueError(f"No folders returned for {label}.")
                    choice = choose(label, choices)
                    if choice == "select":
                        value = get(current, selector["itemValuePath"])
                        if value is None:
                            raise ValueError(f"The folder picker returned no value for {label}.")
                        return value
                    if choice == "up":
                        stack.pop()
                    else:
                        stack.append((choice, extension))
            extension = schema.get("x-ms-dynamic-values") or schema.get("x-ms-dynamic-list")
            # Designer-only address-book pickers are not exposed by the connector API.
            if (extension and not spec(extension).get("operationId")
                    and (spec(extension).get("builtInOperation") or spec(extension).get("capability"))):
                extension = None
            if extension:
                extension = spec(extension)
                items = get(dynamic(extension), extension.get("value-collection") or extension.get("valueCollection") or extension.get("itemsPath"))
                if not isinstance(items, list) or not items:
                    raise ValueError(f"No choices returned for {label}.")
                choices = [(get(item, extension.get("value-title") or extension.get("valueTitle") or extension.get("itemTitlePath")),
                            get(item, extension.get("value-path") or extension.get("valuePath") or extension.get("itemValuePath")))
                           for item in items]
                if any(title is None or value is None for title, value in choices):
                    raise ValueError(f"Invalid picker response for {label}.")
                return choose(label, choices)
            if "enum" in schema:
                titles = {json.dumps(item["value"]): item["displayName"] for item in schema.get("x-ms-enum-values", [])}
                return choose(label, [(titles.get(json.dumps(value), str(value)), value) for value in schema["enum"]])
            if schema.get("type") == "object" or "properties" in schema:
                return fields(schema.get("properties", {}), schema.get("required", []), path)
            if schema.get("type") == "boolean":
                return choose(label, [("Yes", True), ("No", False)])
            return prompt_value(label, schema, prompt)

        top = {parameter["name"]: parameter for parameter in parameters
               if parameter["in"] in {"path", "query", "header"} and parameter["name"] != "connectionId"}
        required = {name for name, parameter in top.items() if parameter.get("required")}
        fields(top, required, [])
        if body:
            value = collect(body["schema"], "Subscription details", ["body"])
            if value:
                answers["body"] = value
        selected.append({"functionName": function, "operationName": operation_id,
                         "parameters": [{"name": name, "value": value} for name, value in answers.items()
                                        if name in top or name == "body"]})
    if not selected:
        raise ValueError("Select at least one trigger.")
    return selected


def collect_from_connection(outputs, connector, definitions, rest, root, *, prompt=input):
    location = outputs.get("CONNECTOR_NAMESPACE_LOCATION", "westcentralus")
    exported = rest("GET", "https://management.azure.com/subscriptions/" + outputs["AZURE_SUBSCRIPTION_ID"]
                    + "/providers/Microsoft.Web/locations/" + quote(location, safe="")
                    + "/managedApis/" + connector + "?api-version=2016-06-01&export=true")
    swagger = exported.get("properties", {}).get("apiDefinitions", {}).get("value", exported)
    if isinstance(swagger, str):
        swagger = json.loads(swagger)
    connection = root + "/connections/" + quote(outputs["connectorNamespaceConnectionName"], safe="")
    picker = make_picker(swagger, lambda body: rest("POST", connection + "/dynamicInvoke", body))
    return collect_trigger_inputs(swagger, definitions, picker, choose=choose_from_terminal(prompt), prompt=prompt)
