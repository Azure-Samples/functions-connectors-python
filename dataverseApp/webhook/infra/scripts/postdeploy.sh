#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v pwsh >/dev/null 2>&1; then
    echo "ERROR: PowerShell 7.3 or later (pwsh) is required for the Dataverse post-deploy hook." >&2
    exit 1
fi
exec pwsh -NoProfile -File "$SCRIPT_DIR/postdeploy.ps1" "$@"