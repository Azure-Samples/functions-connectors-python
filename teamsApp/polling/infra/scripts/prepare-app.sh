#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pwsh -NoProfile -File "$script_dir/prepare-app.ps1" "$@"
