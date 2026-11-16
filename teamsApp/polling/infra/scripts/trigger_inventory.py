"""Verify sample Poll configuration ownership before a Bicep deployment."""

import json
import os
import tempfile
from urllib.parse import parse_qsl, quote, urlsplit


API_VERSION = "2026-05-01-preview"


def verify_existing(outputs: dict, prefix: str, connector: str, operations: dict, run) -> None:
    segments = [quote(outputs[key], safe="") for key in
                ("AZURE_SUBSCRIPTION_ID", "resourceGroupName", "connectorNamespaceName")]
    collection = (f"https://management.azure.com/subscriptions/{segments[0]}/resourceGroups/{segments[1]}"
                  f"/providers/Microsoft.Web/connectorGateways/{segments[2]}/triggerConfigs")
    target = urlsplit(collection)
    url = collection + "?api-version=" + API_VERSION
    seen = set()
    resources = []
    while url:
        if not isinstance(url, str):
            raise ValueError("Invalid trigger continuation URL.")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc != target.netloc or
                parsed.path.rstrip("/").lower() != target.path.lower() or parsed.fragment or url in seen):
            raise ValueError("Invalid or repeated trigger continuation URL.")
        seen.add(url)
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        if (len({key for key, _ in pairs}) != len(pairs) or
                dict(pairs).get("api-version") != API_VERSION):
            raise ValueError("Invalid trigger continuation parameters.")
        descriptor, filename = tempfile.mkstemp(prefix="poll-inventory-", suffix=".json")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(dict(pairs), stream)
            raw = run("az", "rest", "--method", "get", "--url",
                      f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
                      "--url-parameters", "@" + filename, "-o", "json")
        finally:
            os.remove(filename)
        page = json.loads(raw)
        if (not isinstance(page, dict) or not isinstance(page.get("value"), list) or
                not all(isinstance(item, dict) for item in page["value"])):
            raise ValueError("Invalid trigger configuration inventory.")
        resources.extend(page["value"])
        url = page.get("nextLink")
    for function, operation in operations.items():
        name = f"{prefix}-{function.lower()}"
        expected_id = target.path + "/" + name
        matches = [item for item in resources if
                   str(item.get("name", "")).lower() == name.lower() or
                   str(item.get("id", "")).lower() == expected_id.lower()]
        if not matches:
            continue
        properties = matches[0].get("properties", {})
        if not isinstance(properties, dict) or not isinstance(properties.get("connectionDetails"), dict):
            raise ValueError(f"Refusing to overwrite '{name}': invalid configuration properties.")
        connection = properties["connectionDetails"]
        if (len(matches) != 1 or str(matches[0].get("id", "")).lower() != expected_id.lower() or
                str(matches[0].get("name", "")).lower() != name.lower() or
                properties.get("operationName") != operation or properties.get("deliveryMode") != "Poll" or
                connection.get("connectorName") != connector or
                connection.get("connectionName") != outputs["connectorNamespaceConnectionName"]):
            raise ValueError(f"Refusing to overwrite '{name}': subscription ownership does not match.")
