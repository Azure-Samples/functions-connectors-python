#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project=$(CDPATH= cd -- "$script_dir/../.." && pwd)
helper="$script_dir/setup.py"
python_cmd=${PYTHON:-$(command -v python3 || command -v python || echo python3)}
exec "$python_cmd" "$helper" --mode webhook --project "$project" "$@"