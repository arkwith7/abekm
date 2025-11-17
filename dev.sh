#!/usr/bin/env bash
# Wrapper: moved to ./shell-script/dev.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/shell-script/dev.sh" "$@"
