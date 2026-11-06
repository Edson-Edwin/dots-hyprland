#!/usr/bin/env python3
"""Serial, cancellable thumbnail generation with bounded decoder resources."""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
from urllib.parse import quote

SIZES = {"normal": 128, "large": 256, "x-large": 512, "xx-large": 1024}
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".bmp", ".svg"}
child = None


def stop(signum, frame):
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    raise SystemExit(128 + signum)


def decoder_limits():
    # Pixel-cache limits alone do not bound decoder/library allocations.
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 21))
    resource.setrlimit(resource.RLIMIT_FSIZE, (512 * 1024**2, 512 * 1024**2))


def thumbnail(source, cache, size, lock_fd):
    global child
    source = source.absolute()
    # Match ThumbnailImage.qml's encodeURIComponent, including Unicode names.
    uri = "file://" + quote(str(source), safe="/!~*'()")
    output = cache / (hashlib.md5(uri.encode()).hexdigest() + ".png")
    if output.exists() and output.stat().st_size and output.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return True
    fd, name = tempfile.mkstemp(prefix=".thumbnail-", suffix=".png", dir=cache)
    os.close(fd)
    temporary = Path(name)
    try:
        command = ["magick", "-limit", "thread", "1", "-limit", "memory", "64MiB",
                   "-limit", "map", "128MiB", "-limit", "disk", "256MiB",
                   "-limit", "time", "20", "-define", f"jpeg:size={size * 2}x{size * 2}",
                   str(source) + "[0]", "-auto-orient", "-thumbnail", f"{size}x{size}>",
                   "-strip", "-set", "Thumb::URI", uri,
                   "-set", "Thumb::MTime", str(int(source.stat().st_mtime)), str(temporary)]
        child = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 preexec_fn=decoder_limits, pass_fds=(lock_fd,))
        try:
            code = child.wait(timeout=25)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            return False
        if code == 0 and temporary.stat().st_size:
            os.replace(temporary, output)
            return True
        return False
    finally:
        child = None
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", "-s", choices=SIZES, default="normal")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--directory", "-d", type=Path)
    target.add_argument("--file", "-f", type=Path)
    parser.add_argument("--machine_progress", action="store_true")
    args = parser.parse_args()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "thumbnails"
    cache = base / args.size
    cache.mkdir(parents=True, exist_ok=True)
    # The decoder inherits the lock so killing the controller cannot leave
    # an unaccounted parallel decoder behind.
    with (base / ".ii-thumbnail.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.directory:
            files = sorted((p for p in args.directory.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS), key=str)
        else:
            files = [args.file] if args.file.is_file() and args.file.suffix.lower() in EXTENSIONS else []
        failed = 0
        for count, source in enumerate(files, 1):
            try:
                success = thumbnail(source, cache, SIZES[args.size], lock.fileno())
            except OSError as error:
                print(f"Thumbnail skipped: {source}: {error}", file=sys.stderr)
                success = False
            if not success:
                failed += 1
                print(f"Thumbnail skipped (unsupported, corrupt, or resource limit): {source}", file=sys.stderr)
            if args.machine_progress:
                print(f"PROGRESS {count}/{len(files)}", flush=True)
                if success and "\n" not in str(source) and "\r" not in str(source):
                    print(f"FILE {source.absolute()}", flush=True)
        if args.file and (failed or not files):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
