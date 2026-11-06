#!/usr/bin/env python3
"""Sort only loose regular files in the user's XDG Downloads directory."""
import argparse
import ctypes
import errno
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

HERE = Path(__file__).resolve().parent
PREFIX = "ii-downloads-organizer"
PERIODS = ("hourly", "daily", "weekly")
PARTIAL = (".crdownload", ".part", ".partial", ".download", ".tmp", ".temp",
           ".opdownload", ".filepart", ".aria2")
DIRFLAGS = os.O_DIRECTORY | os.O_RDONLY | os.O_NOFOLLOW


def downloads():
    value = subprocess.check_output(["xdg-user-dir", "DOWNLOAD"], text=True, timeout=4).rstrip("\n")
    p = Path(value)
    home = Path.home().resolve()
    if not value or not p.is_absolute() or p.resolve() == home or p.resolve() in home.parents:
        raise ValueError("Set a dedicated Downloads folder in your XDG user directories first.")
    return p.resolve(strict=True)


def group(name):
    lower = name.lower()
    for ext in ("tar.gz", "tar.bz2", "tar.xz", "tar.zst", "tar.lz", "tar.lzma"):
        if lower.endswith("." + ext):
            return ext
    ext = Path(lower).suffix[1:]
    if not ext:
        return "No extension"
    return ext if re.fullmatch(r"[\w+-]{1,40}", ext) else "Other extensions"


def sort_files(folder, automatic=False):
    fd = os.open(folder, DIRFLAGS)
    moved = skipped = failed = 0
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rename = ctypes.CDLL(None, use_errno=True).renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        now = time.time()
        for name in sorted(os.listdir(fd)):
            if name.startswith("."):
                continue
            try:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    continue
                if (name.lower().endswith(PARTIAL) or os.path.exists(Path(folder) / (name + ".aria2"))
                        or (automatic and now - info.st_mtime < 120)):
                    skipped += 1
                    continue
                dest = group(name)
                try:
                    os.mkdir(dest, dir_fd=fd)
                except FileExistsError:
                    pass
                target = os.open(dest, DIRFLAGS, dir_fd=fd)
                try:
                    suffix = "".join(Path(name).suffixes[-2:]) if dest.startswith("tar.") else Path(name).suffix
                    stem = name[:-len(suffix)] if suffix else name
                    n = 1
                    while True:
                        candidate = name if n == 1 else f"{stem} ({n}){suffix}"
                        # Atomic rename with RENAME_NOREPLACE. Never follow a symlinked
                        # destination folder or overwrite an existing filename.
                        if rename(fd, os.fsencode(name), target, os.fsencode(candidate), 1) == 0:
                            moved += 1
                            break
                        code = ctypes.get_errno()
                        if code != errno.EEXIST:
                            raise OSError(code, os.strerror(code))
                        n += 1
                finally:
                    os.close(target)
            except FileNotFoundError:
                skipped += 1
            except OSError:
                failed += 1
    finally:
        os.close(fd)
    return moved, skipped, failed


def systemctl(*args):
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=15)


def must(*args):
    result = systemctl(*args)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "The user timer could not be updated.")


def timer(period):
    return f"{PREFIX}@{period}.timer"


def schedules():
    # A template's unit-file state doesn't identify the enabled instance.
    # Read the actual Wants links that systemctl enable creates.
    roots = [Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")]
    if runtime := os.getenv("XDG_RUNTIME_DIR"):
        roots.append(Path(runtime))
    return [p for p in PERIODS if any(
        (root / "systemd/user/timers.target.wants" / timer(p)).is_symlink() for root in roots)]



def set_schedule(choice):
    active = schedules()
    if choice != "off":
        must("link", str(HERE / f"{PREFIX}.service"), str(HERE / f"{PREFIX}@.timer"))
        must("daemon-reload")
        must("enable", "--now", timer(choice))
    for period in active:
        if period != choice:
            must("disable", "--now", timer(period))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "run", "scheduled", "schedule"))
    parser.add_argument("period", nargs="?", choices=("off", *PERIODS))
    args = parser.parse_args()
    msg = ""
    try:
        if args.action in ("run", "scheduled"):
            moved, skipped, failed = sort_files(downloads(), args.action == "scheduled")
            msg = f"Moved {moved} file(s)."
            if skipped:
                msg += f" Skipped {skipped} incomplete or recent file(s)."
            if failed:
                msg += f" Could not move {failed} file(s); check folder permissions or conflicting names."
            if args.action == "scheduled":
                print(msg)
                return int(bool(failed))
        elif args.action == "schedule":
            if not args.period:
                raise ValueError("Choose a schedule first.")
            if args.period != "off":
                downloads()
            set_schedule(args.period)
            msg = "Automatic sorting is off." if args.period == "off" else "Schedule saved."
        print(json.dumps({"schedule": ", ".join(schedules()) or "off", "message": msg}))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as err:
        print(json.dumps({"message": str(err)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
