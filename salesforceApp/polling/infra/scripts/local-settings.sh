# Sourced by postdeploy.sh; both shells use the same JSON implementation.
salesforce_setup() {
    "${PYTHON:-python}" "$script_dir/setup.py" \
        --mode polling --project "$script_dir/../.." "$@"
}