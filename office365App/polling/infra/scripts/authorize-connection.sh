#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python_cmd=${PYTHON:-$(command -v python3 || command -v python || echo python3)}
"$python_cmd" "$script_dir/select_sources.py"
