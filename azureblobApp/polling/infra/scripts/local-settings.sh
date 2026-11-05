connector_jq() { command jq --binary "$@"; }

write_local_settings() (
    set -euo pipefail
    umask 077
    local target="$app_dir/local.settings.json" temp='' result force="${2:-false}"
    if [[ -e "$target" || -L "$target" ]]; then
        [[ -f "$target" && ! -L "$target" ]] || { echo 'Settings must be a regular file, not a directory or link.' >&2; exit 1; }
        if [[ "$force" != true ]]; then echo 'Existing local.settings.json preserved byte-for-byte.'; exit 0; fi
    fi
    cleanup_local_settings() {
        result=$?
        trap - EXIT
        if [[ -n "$temp" ]]; then
            rm -f -- "$temp" || { echo 'Settings staging cleanup failed.' >&2; [[ "$result" -ne 0 ]] || result=1; }
        fi
        exit "$result"
    }
    trap cleanup_local_settings EXIT
    temp=$(mktemp "$app_dir/.local-settings.XXXXXXXX")
    printf '%s\n' "$1" > "$temp"
    if [[ "$force" == true ]]; then
        if [[ -e "$target" || -L "$target" ]]; then
            [[ -f "$target" && ! -L "$target" ]] || { echo 'Settings must be a regular file.' >&2; exit 1; }
        fi
        mv -fT -- "$temp" "$target"
    else
        link "$temp" "$target"
    fi
)