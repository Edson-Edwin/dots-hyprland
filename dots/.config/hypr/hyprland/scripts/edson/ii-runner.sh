#!/usr/bin/env bash
# Use KDE's installed runner for applications, calculations and plugin searches.
set -eu
if command -v krunner >/dev/null 2>&1; then
    exec env QT_QPA_PLATFORM=wayland krunner
fi
exec fuzzel
