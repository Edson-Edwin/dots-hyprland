#!/usr/bin/env bash
# Preserve the upstream entry point without a decoder per file.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/safe-thumbnails.py" "$@"
