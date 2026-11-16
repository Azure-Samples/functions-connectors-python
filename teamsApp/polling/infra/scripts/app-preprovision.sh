#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bash "$script_dir/prepare-app.sh"
"${PYTHON:-python}" "$script_dir/detect_app.py"
