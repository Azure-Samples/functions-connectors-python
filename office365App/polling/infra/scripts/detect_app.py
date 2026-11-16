"""Determine whether the sample Function App already exists without reading its settings."""

import json
import os
import shutil
import subprocess
import sys


def command(program: str, *arguments: str) -> str:
    executable = shutil.which(program + ".cmd") if os.name == "nt" else None
    executable = executable or shutil.which(program)
    if not executable:
        raise RuntimeError(f"Required command '{program}' is not installed.")
    result = subprocess.run(
        [executable, *arguments], capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode:
        raise RuntimeError(f"'{program}' failed while checking the Function App.")
    return result.stdout


def main() -> None:
    outputs = json.loads(command("azd", "env", "get-values", "--output", "json"))
    if not isinstance(outputs, dict):
        raise ValueError("Invalid azd environment outputs.")
    for name in ("AZURE_SUBSCRIPTION_ID", "resourceGroupName", "functionAppName"):
        if not isinstance(outputs.get(name), str) or not outputs[name].strip():
            raise ValueError(f"Missing azd output '{name}'. Run azd provision base first.")

    names = json.loads(command(
        "az", "functionapp", "list", "--subscription", outputs["AZURE_SUBSCRIPTION_ID"],
        "--resource-group", outputs["resourceGroupName"], "--query", "[].name", "--output", "json"
    ))
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError("Invalid Function App inventory response.")
    matches = [name for name in names if name.casefold() == outputs["functionAppName"].casefold()]
    if len(matches) > 1:
        raise ValueError("Ambiguous Function App inventory response.")
    command("azd", "env", "set", "POLLING_FUNCTION_APP_EXISTS", str(bool(matches)).lower())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
