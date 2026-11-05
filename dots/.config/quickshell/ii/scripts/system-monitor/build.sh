#!/usr/bin/env bash
set -eu
target="${XDG_DATA_HOME:-$HOME/.local/share}/illogical-impulse/system-monitor"
mkdir -p "$target"
tmp=$(mktemp "$target/.process-scan.XXXXXX")
trap 'rm -f "$tmp"' EXIT
rustc --edition=2021 -C opt-level=2 -C strip=symbols "$(dirname "$0")/scan.rs" -o "$tmp"
chmod 755 "$tmp"
mv -f "$tmp" "$target/process-scan"
