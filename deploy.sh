#!/usr/bin/env bash
# Wrapper: moved to ./shell-script/deploy.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/shell-script/deploy.sh" "$@"
