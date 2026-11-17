# Copyright (c) Microsoft Corporation.  All rights reserved.

"""Keep every sample on the supported non-preview extension bundle."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BundleVersionTests(unittest.TestCase):
    """Check every deployable sample rather than a fixed connector list."""

    def test_all_samples_use_the_stable_bundle(self):
        hosts = sorted(ROOT.glob("*App/**/host.json"))
        self.assertTrue(hosts, "No sample host configurations found.")
        for host in hosts:
            with self.subTest(sample=host.relative_to(ROOT).as_posix()):
                bundle = json.loads(host.read_text(encoding="utf-8"))["extensionBundle"]
                self.assertEqual(bundle["id"], "Microsoft.Azure.Functions.ExtensionBundle")
                self.assertEqual(bundle["version"], "[4.41.2, 5.0.0)")


if __name__ == "__main__":
    unittest.main()