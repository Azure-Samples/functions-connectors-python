# Copyright (c) .NET Foundation. All rights reserved.
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Select Azure DevOps sources using the authenticated connector's metadata."""

import json
import re
from urllib.parse import quote


def resolve(swagger: dict, schema: dict, visited: frozenset = frozenset()) -> dict:
    if not isinstance(schema, dict):
        raise ValueError("Invalid connector parameter schema.")
    reference = schema.get("$ref")
    if not reference:
        return schema
    if not isinstance(reference, str) or not reference.startswith("#/") or reference in visited:
        raise ValueError("Unsupported or cyclic schema reference.")
    target = swagger
    for part in reference[2:].split("/"):
        target = target[part.replace("~1", "/").replace("~0", "~")]
    return {**resolve(swagger, target, visited | {reference}),
            **{key: value for key, value in schema.items() if key != "$ref"}}


def operation(swagger: dict, operation_id: str) -> tuple[str, str, list[dict]]:
    matches = []
    for route, methods in swagger["paths"].items():
        for method, definition in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if definition.get("operationId") == operation_id:
                merged = {}
                for parameter in methods.get("parameters", []) + definition.get("parameters", []):
                    parameter = resolve(swagger, parameter)
                    merged[(parameter.get("in"), parameter.get("name"))] = parameter
                matches.append((route, method, list(merged.values())))
    if len(matches) != 1:
        raise ValueError(f"Connector must expose exactly one '{operation_id}' operation.")
    return matches[0]


def parameters_for(swagger: dict, operation_id: str) -> list[dict]:
    return [parameter for parameter in operation(swagger, operation_id)[2]
            if parameter.get("name") != "connectionId"
            and parameter.get("x-ms-visibility") != "internal" and not parameter.get("readOnly")]


def operation_request(swagger: dict, operation_id: str, values: dict) -> dict:
    route, method, parameters = operation(swagger, operation_id)
    route = re.sub(r"^/\{connectionId\}", "", route)
    if not route.startswith("/"):
        raise ValueError(f"Invalid connector picker route for {operation_id}.")
    request = {"method": method.upper(), "path": route}
    for parameter in parameters:
        name = parameter.get("name")
        if name == "connectionId":
            continue
        if name not in values:
            if parameter.get("required"):
                raise ValueError(f"{operation_id} requires {name}.")
            continue
        value = values[name]
        if parameter.get("in") == "path":
            encoded = quote(str(value), safe="")
            if parameter.get("x-ms-url-encoding") == "double":
                encoded = quote(encoded, safe="")
            request["path"] = request["path"].replace("{" + name + "}", encoded)
        elif parameter.get("in") == "query":
            request.setdefault("queries", {})[name] = value
        elif parameter.get("in") == "body":
            request["body"] = value
        else:
            raise ValueError(f"Unsupported connector picker parameter for {operation_id}.")
    if re.search(r"\{[^}]+\}", request["path"]):
        raise ValueError(f"Unresolved connector picker path for {operation_id}.")
    return request


def make_picker(swagger: dict, request):
    cache = {}

    def invoke(operation_id: str, values: dict):
        key = json.dumps([operation_id, values], sort_keys=True)
        if key not in cache:
            result = request({"request": operation_request(swagger, operation_id, values)})
            response = result.get("response") if isinstance(result, dict) else None
            if not isinstance(response, dict) or str(response.get("statusCode")).upper() not in {"200", "201", "OK", "CREATED"}:
                raise ValueError(f"Connector picker {operation_id} failed. Check connection and source permissions.")
            body = response.get("body")
            cache[key] = json.loads(body) if isinstance(body, str) else body
        return cache[key]

    return invoke


def choose_from_terminal(prompt):
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


def _get(value, path):
    if not path:
        return value
    if isinstance(value, dict) and path in value:
        return value[path]
    for part in re.split(r"[/.]", path):
        if not part:
            continue
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def _picker_spec(extension):
    if not isinstance(extension, dict):
        raise ValueError("Invalid connector picker metadata.")
    state = extension.get("dynamicState") or {}
    if not extension.get("operationId") and isinstance(state, dict):
        extension = {**extension, **state.get("extension", state)}
    if not extension.get("operationId"):
        raise ValueError("Connector picker metadata has no operation ID.")
    return extension


class _NoChoices(ValueError):
    pass


def collect_trigger_inputs(swagger, operations, invoke, *, choose, prompt,
                           optional_filters=False, skip_unavailable=False):
    definitions = [(name, operation_id) for name, operation_id in operations.items()
                   if choose(f"Configure {name}?", [("Skip", False), ("Configure", True)])]
    if not definitions:
        raise ValueError("Select at least one Azure DevOps trigger.")
    selected = []
    for function, operation_id in definitions:
        schemas = parameters_for(swagger, operation_id)
        if any(schema.get("in") not in {"path", "query"} or schema.get("type") != "string"
               or not isinstance(schema.get("name"), str) for schema in schemas):
            raise ValueError(f"Unsupported trigger input schema for {operation_id}; no values were guessed.")
        by_name = {schema["name"]: schema for schema in schemas}
        answers, active = {}, set()

        def collect(schema):
            name = schema["name"]
            if name in answers:
                return answers[name]
            if name in active:
                raise ValueError(f"Cyclic connector picker dependencies for {name}.")
            active.add(name)
            try:
                label = schema.get("x-ms-summary") or schema.get("title") or name
                extension = schema.get("x-ms-dynamic-values") or schema.get("x-ms-dynamic-list")
                if extension:
                    spec = _picker_spec(extension)
                    bindings = spec.get("parameters") or {}
                    if not isinstance(bindings, dict):
                        raise ValueError(f"Invalid connector picker parameters for {label}.")
                    values = {}
                    for key, binding in bindings.items():
                        reference = (binding.get("parameter") or binding.get("parameterReference")) if isinstance(binding, dict) else None
                        if reference:
                            if reference not in by_name:
                                raise ValueError(f"Missing picker prerequisite {reference} for {label}.")
                            values[key] = collect(by_name[reference])
                        else:
                            values[key] = binding.get("value", binding) if isinstance(binding, dict) else binding
                    result = invoke(spec["operationId"], values)
                    collection_path = spec.get("value-collection") or spec.get("valueCollection") or spec.get("itemsPath")
                    items = _get(result, collection_path)
                    if not isinstance(items, list):
                        raise ValueError(f"Invalid connector picker response for {label}.")
                    if not items:
                        raise _NoChoices(f"No choices returned for {label}.")
                    value_path = spec.get("value-path") or spec.get("valuePath") or spec.get("itemValuePath")
                    title_path = spec.get("value-title") or spec.get("valueTitle") or spec.get("itemTitlePath")
                    choices = [(_get(item, title_path), _get(item, value_path)) for item in items]
                    if any(not isinstance(title, str) or not title or not isinstance(value, str) or not value
                           for title, value in choices):
                        raise ValueError(f"Invalid connector picker choices for {label}.")
                    value = choose(label, choices)
                    if value not in [item[1] for item in choices]:
                        raise ValueError(f"Invalid selection for {label}.")
                elif "enum" in schema:
                    choices = [(str(value) or "Any (no filter)", value) for value in schema["enum"]]
                    value = choose(label, choices)
                else:
                    while True:
                        value = prompt(f"{label}: ").strip()
                        if (value and len(value) >= schema.get("minLength", 0)
                                and len(value) <= schema.get("maxLength", float("inf"))
                                and ("pattern" not in schema or re.search(schema["pattern"], value))):
                            break
                        print("Enter a non-empty value matching the requested constraints.")
                answers[name] = value
                return value
            finally:
                active.remove(name)

        try:
            for schema in schemas:
                if schema.get("required"):
                    collect(schema)
            if optional_filters:
                for schema in schemas:
                    if schema["name"] not in answers and choose(
                            f"Configure {schema.get('x-ms-summary') or schema['name']} (optional)?",
                            [("Skip", False), ("Configure", True)]):
                        collect(schema)
        except _NoChoices as error:
            if not skip_unavailable:
                raise
            print(f"Skipped {function}: {error}")
            continue
        selected.append({"functionName": function, "operationName": operation_id,
                         "parameters": [{"name": schema["name"], "value": answers[schema["name"]]}
                                        for schema in schemas if schema["name"] in answers]})
    if not selected:
        raise ValueError("No Azure DevOps triggers were configured.")
    return selected
