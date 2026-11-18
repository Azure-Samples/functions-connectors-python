# Sourced by postdeploy.sh; both shells use the same JSON implementation.
salesforce_setup() {
    python_cmd=${PYTHON:-$(command -v python3 || command -v python || echo python3)}
    "$python_cmd" "$script_dir/setup.py" \
        --mode polling --project "$script_dir/../.." "$@"
}