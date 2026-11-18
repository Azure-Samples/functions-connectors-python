# Sourced by postdeploy.sh; keep JSON and local settings logic identical on both shells.
office365_setup() {
    python_cmd=${PYTHON:-$(command -v python3 || command -v python || echo python3)}
    "$python_cmd" "$script_dir/setup.py" \
        --mode polling --project "$script_dir/../.." "$@"
}