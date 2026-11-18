#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_cmd=${PYTHON:-$(command -v python3 || command -v python || echo python3)}
"$python_cmd" "$script_dir/select_sources.py"
