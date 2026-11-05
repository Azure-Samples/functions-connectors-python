#!/usr/bin/env bash
set -euo pipefail
umask 077
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/local-settings.sh"
sharepoint_setup "$@"