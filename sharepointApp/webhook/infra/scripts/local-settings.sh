#!/usr/bin/env bash
sharepoint_setup() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  python_cmd=${PYTHON:-$(command -v python3 || command -v python || echo python3)}
  "$python_cmd" "$script_dir/setup.py" --mode webhook --project "$script_dir/../.." "$@"
}