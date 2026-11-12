#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project=$(CDPATH= cd -- "$script_dir/../.." && pwd)
helper="$script_dir/../../../scripts/setup.py"
exec python3 "$helper" --mode polling --project "$project" "$@"