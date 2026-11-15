# Copyright (c) .NET Foundation. All rights reserved.
# Licensed under the MIT License.

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
SUBSCRIPTION = "11111111-2222-3333-4444-555555555555"
OUTPUTS = {
    "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION,
    "resourceGroupName": "rg-test",
    "connectorNamespaceName": "namespace-test",
    "connectorNamespaceConnectionName": "connection-test-mi",
    "connectorPollingEndpoint": "https://example.test",
    "triggerConfigSettings": {
        "OnAzureBlobUpdatedFileTriggerConfigName": "trigger-test"
    },
    "functionAppName": "function-test",
    "functionAppDefaultHostname": "function-test.example.test",
    "monitoredStorageAccountName": "storagetest",
    "monitoredContainerName": "input",
}

FAKE_CLI = r"""
import json
import os
from pathlib import Path
import sys

if Path(sys.argv[0]).name == "azd":
    print(os.environ["MOCK_OUTPUTS"])
    sys.exit(0)

args = sys.argv[1:]
with open(os.environ["MOCK_CALLS"], "a", encoding="utf-8") as calls:
    calls.write(json.dumps(args) + "\n")

if args[:2] == ["extension", "show"]:
    print("connector-namespace")
    sys.exit(0)

if "--subscription" not in args or args[args.index("--subscription") + 1] != os.environ["MOCK_SUBSCRIPTION"]:
    print("incorrect Azure subscription", file=sys.stderr)
    sys.exit(1)

if args[0] == "rest":
    url = args[args.index("--url") + 1]
    if url != os.environ["MOCK_CONNECTION_URI"] or "--query" not in args:
        print("incorrect connection request", file=sys.stderr)
        sys.exit(1)
    if os.environ["MOCK_SCENARIO"] == "read-error":
        print("simulated ARM read failure", file=sys.stderr)
        sys.exit(1)
    auth = "OAuth" if os.environ["MOCK_SCENARIO"] == "wrong-auth" else "managedIdentityAuth"
    print(json.dumps({"properties": {"overallStatus": "Ready", "parameterValueSet": {"name": auth}}}))
elif args[:3] == ["connector-namespace", "connection", "show"]:
    print(json.dumps({"properties": {"overallStatus": "Ready"}}))
elif args[:3] == ["connector-namespace", "trigger", "list"]:
    print("[]")
elif args[:3] == ["functionapp", "keys", "list"]:
    print("test-key")
elif args[:3] in (["connector-namespace", "trigger", "create"], ["connector-namespace", "trigger", "update"]):
    pass
else:
    print("unexpected Azure CLI command", file=sys.stderr)
    sys.exit(1)
"""


class PostdeploySubscriptionTests(unittest.TestCase):
    def run_hook(self, mode, shell, scenario):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / mode / "infra" / "scripts"
            scripts.mkdir(parents=True)
            extension = "ps1" if shell == "pwsh" else "sh"
            for name in ("postdeploy", "local-settings"):
                filename = f"{name}.{extension}"
                shutil.copy2(APP_ROOT / mode / "infra" / "scripts" / filename, scripts)

            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake_cli = bin_dir / "fake-cli"
            fake_cli.write_text(f"#!{sys.executable}\n{FAKE_CLI}", encoding="utf-8")
            fake_cli.chmod(0o755)
            for name in ("az", "azd"):
                (bin_dir / name).symlink_to(fake_cli)

            outputs = dict(OUTPUTS)
            if scenario == "missing-subscription":
                del outputs["AZURE_SUBSCRIPTION_ID"]
            env = os.environ.copy()
            env.pop("BASH_ENV", None)
            env.pop("ENV", None)
            env.update({
                "HOME": str(root),
                "TMPDIR": str(root),
                "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
                "MOCK_OUTPUTS": json.dumps(outputs),
                "MOCK_CALLS": str(root / "calls.jsonl"),
                "MOCK_SUBSCRIPTION": SUBSCRIPTION,
                "MOCK_SCENARIO": scenario,
                "MOCK_CONNECTION_URI": (
                    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-test/providers/"
                    "Microsoft.Web/connectorGateways/namespace-test/connections/"
                    "connection-test-mi?api-version=2026-05-01-preview"
                ),
            })
            script = scripts / f"postdeploy.{extension}"
            command = (
                ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)]
                if shell == "pwsh"
                else ["bash", str(script)]
            )
            result = subprocess.run(
                command, cwd=scripts.parents[1], env=env, capture_output=True, text=True, timeout=30
            )
            calls_path = root / "calls.jsonl"
            calls = (
                [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines()]
                if calls_path.exists()
                else []
            )
            return result, calls

    def check_hooks(self, shell):
        for mode in ("polling", "webhook"):
            for scenario in ("ready", "wrong-auth", "read-error", "missing-subscription"):
                with self.subTest(mode=mode, shell=shell, scenario=scenario):
                    result, calls = self.run_hook(mode, shell, scenario)
                    output = result.stdout + result.stderr
                    if scenario == "ready":
                        self.assertEqual(result.returncode, 0, output)
                        self.assertTrue(any(call[0] == "rest" for call in calls))
                        if mode == "webhook":
                            self.assertTrue(any(call[:3] == ["connector-namespace", "trigger", "create"] for call in calls))
                    else:
                        self.assertNotEqual(result.returncode, 0, output)
                        self.assertFalse(any(call[:3] == ["connector-namespace", "trigger", "create"] for call in calls))
                        if scenario == "wrong-auth":
                            self.assertIn("managedIdentityAuth", output)
                        elif scenario == "read-error":
                            self.assertIn("simulated ARM read failure", output)
                        else:
                            self.assertFalse(any(call[0] == "rest" for call in calls))

    @unittest.skipUnless(os.name == "posix" and shutil.which("bash") and shutil.which("jq"), "requires Bash and jq")
    def test_bash_hooks(self):
        self.check_hooks("bash")

    @unittest.skipUnless(os.name == "posix" and shutil.which("pwsh"), "requires PowerShell on POSIX")
    def test_powershell_hooks(self):
        self.check_hooks("pwsh")


if __name__ == "__main__":
    unittest.main()
