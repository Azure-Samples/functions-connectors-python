# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Compatibility entry point; new hooks use each mode's own complete helper."""

import argparse
import runpy
from pathlib import Path


def main() -> None:
    """Forward legacy command-line calls without sharing runtime implementation."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=("polling", "webhook"), required=True)
    options, _ = parser.parse_known_args()
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / options.mode / "infra/scripts/setup.py"),
        run_name="__main__",
    )


if __name__ == "__main__":
    main()