#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"${PYTHON:-python}" "$script_dir/detect_app.py"
