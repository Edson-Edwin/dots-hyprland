#!/usr/bin/env bash
set -eu
exec /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/voice-ai/app.py" "${1:-menu}"
