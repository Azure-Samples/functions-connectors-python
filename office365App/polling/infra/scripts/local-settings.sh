# Sourced by postdeploy.sh; keep JSON and local settings logic identical on both shells.
office365_setup() {
    "${PYTHON:-python}" "$script_dir/../../../scripts/setup.py" \
        --mode polling --project "$script_dir/../.." "$@"
}