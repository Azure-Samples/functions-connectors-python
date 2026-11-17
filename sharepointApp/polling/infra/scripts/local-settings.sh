#!/usr/bin/env bash
sharepoint_setup() {
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  "${PYTHON:-python}" "$script_dir/setup.py" --mode polling --project "$script_dir/../.." "$@"
}