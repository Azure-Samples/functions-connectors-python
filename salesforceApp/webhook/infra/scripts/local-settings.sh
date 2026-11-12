# Sourced by postdeploy.sh; both shells use the same JSON implementation.
salesforce_setup() {
    "${PYTHON:-python}" "$script_dir/../../../scripts/setup.py" \
        --mode webhook --project "$script_dir/../.." "$@"
}