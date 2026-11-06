#!/usr/bin/env python3
"""Named Material palettes for the existing Illogical Impulse theme pipeline."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

# These are coordinated Material palettes, not copies of third-party themes.
THEMES = {
    "Ocean": {"color": "#7aa2f7", "mode": "dark", "type": "scheme-tonal-spot"},
    "Nord inspired": {"color": "#88c0d0", "mode": "dark", "type": "scheme-neutral"},
    "Forest": {"color": "#a7c080", "mode": "dark", "type": "scheme-tonal-spot"},
    "Plum": {"color": "#cba6f7", "mode": "dark", "type": "scheme-tonal-spot"},
    "Amber": {"color": "#e5a45b", "mode": "dark", "type": "scheme-tonal-spot"},
    "Graphite": {"color": "#9ca3af", "mode": "dark", "type": "scheme-monochrome"},
    "Paper (light)": {"color": "#5271a6", "mode": "light", "type": "scheme-tonal-spot"},
}
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "ii-themes"
SHELL = CONFIG / "illogical-impulse/config.json"
SWITCH = CONFIG / "quickshell/ii/scripts/colors/switchwall.sh"


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".ii-theme-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        if path.exists():
            os.chmod(name, path.stat().st_mode & 0o777)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


_notification_id = None

def notify(title, detail=""):
    global _notification_id
    command = ["notify-send", "--print-id", "--app-name=Desktop themes",
               "--icon=preferences-desktop-theme", "--expire-time=2800"]
    if _notification_id is not None:
        command.append(f"--replace-id={_notification_id}")
    result = subprocess.run([*command, title, detail], text=True, capture_output=True)
    if result.returncode == 0 and result.stdout.strip().isdigit():
        _notification_id = int(result.stdout.strip())


def current_theme():
    data = json.loads(SHELL.read_text())
    palette = data.get("appearance", {}).get("palette", {})
    generated = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "quickshell/user/generated/colors.json"
    mode = "dark"
    if generated.exists():
        colors = json.loads(generated.read_text())
        background = colors.get("background", "#141313").lstrip("#")
        channels = [int(background[i:i+2], 16) for i in (0, 2, 4)]
        mode = "dark" if (max(channels) + min(channels)) / 510 < 0.5 else "light"
    return {"color": palette.get("accentColor") or "clear", "mode": mode,
            "type": palette.get("type", "auto")}


def command_for(theme):
    return ["bash", str(SWITCH), "--noswitch", "--color", theme["color"],
            "--mode", theme["mode"], "--type", theme["type"]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("theme", nargs="?", choices=list(THEMES) + ["Wallpaper colors", "Restore previous"])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--check", action="store_true", help="Print the planned command without changing anything")
    args = parser.parse_args()
    if args.list:
        print("\n".join(THEMES))
        return 0
    selected = args.theme
    if not selected:
        labels = list(THEMES) + ["Wallpaper colors"]
        if (STATE / "previous.json").exists(): labels.append("Restore previous")
        # Dismiss only the theme menu. Palette generation runs separately after selection.
        picker = "/usr/bin/fuzzel --namespace=ii-theme-picker "
        closed = subprocess.run(["pkill", "-TERM", "-u", str(os.getuid()), "-f", "^" + picker])
        if closed.returncode == 0:
            return 0
        # A keyboard-invoked layer needs focus on map, before the shortcut is released.
        choice = subprocess.run(["/usr/bin/fuzzel", "--namespace=ii-theme-picker",
                                 "--keyboard-focus=exclusive", "--dmenu", "--prompt", "Theme: ", "--width", "36",
                                 "--lines", str(len(labels))], input="\n".join(labels), text=True, capture_output=True)
        if choice.returncode: return 0
        selected = choice.stdout.strip()
        if selected not in labels: return 0
    theme = THEMES.get(selected)
    if selected == "Wallpaper colors": theme = {"color": "clear", "mode": current_theme()["mode"], "type": "auto"}
    elif selected == "Restore previous": theme = json.loads((STATE / "previous.json").read_text())
    command = command_for(theme)
    if args.check:
        print(json.dumps(command))
        return 0
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "apply.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            notify("Applying theme", "Please wait for the current change.")
            return 1
        # Validate prerequisites before changing a saved preference.
        venv = Path.home() / ".local/state/quickshell/.venv"
        subprocess.run([str(venv / "bin/python"), "-c", "import PIL, materialyoucolor"], check=True)
        if not SWITCH.is_file(): raise ValueError("Wallpaper/theme script is missing")
        previous = current_theme()
        atomic_json(STATE / "previous.json", previous)
        config = json.loads(SHELL.read_text())
        config.setdefault("appearance", {}).setdefault("palette", {})["type"] = theme["type"]
        atomic_json(SHELL, config)
        environment = os.environ.copy()
        environment["ILLOGICAL_IMPULSE_VIRTUAL_ENV"] = str(Path.home() / ".local/state/quickshell/.venv")
        environment.update(MAGICK_THREAD_LIMIT="1", MAGICK_MEMORY_LIMIT="64MiB",
                           MAGICK_MAP_LIMIT="128MiB", MAGICK_DISK_LIMIT="256MiB")
        notify("Applying theme", selected)
        started = time.time_ns()
        with (STATE / "last-apply.log").open("w") as log:
            process = subprocess.Popen(command, env=environment, stdout=log, stderr=log, start_new_session=True)
            try:
                code = process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                code = 124
        generated = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "quickshell/user/generated"
        # The upstream shell script does not propagate every generator failure.
        for output in (generated / "colors.json", generated / "material_colors.scss"):
            if not output.exists() or output.stat().st_size < 100 or output.stat().st_mtime_ns < started:
                code = code or 1
        if code:
            notify("Theme change failed", "Choose Restore previous. Details in " + str(STATE / "last-apply.log"))
            return code
        atomic_json(STATE / "current.json", {"name": selected, **theme})
        notify("Theme applied", selected)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        notify("Theme change failed", str(error))
        sys.exit(1)
