#!/usr/bin/env python3
"""Fill an external display when mirroring. Only change live monitor rules."""
import json
import subprocess
import sys
import time


def ctl(*args):
    p = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=5)
    if p.returncode or (args[0] == "eval" and "error" in p.stdout.lower()):
        raise RuntimeError((p.stderr or p.stdout).strip() or "Hyprland rejected the layout.")
    return p.stdout


def outputs():
    return {m["name"]: m for m in json.loads(ctl("-j", "monitors", "all"))
            if not m.get("disabled") and m["width"] > 0}


def mirror(m):
    return m.get("mirrorOf") not in ("none", "", None)


def rule(m, mirror_of="", position=None):
    pos = position or f'{m["x"]}x{m["y"]}'
    # Use advertised preferred timings. Preserve each screen's rotation and UI scale.
    parts = {"output": m["name"], "mode": "preferred", "position": pos,
             "scale": m["scale"], "transform": m["transform"], "mirror": mirror_of}
    return "hl.monitor({" + ",".join(f"{k}={json.dumps(v)}" for k, v in parts.items()) + "})"


def until(check):
    for _ in range(20):
        if check(outputs()):
            return
        time.sleep(.12)
    raise RuntimeError("Hyprland did not confirm the requested display layout.")


def apply():
    active = outputs()
    laptop = next((name for name in active if name.startswith(("eDP", "LVDS", "DSI"))), None)
    if not laptop:
        return "No active built-in laptop display."
    external = [name for name in active if name != laptop and not name.startswith(("HEADLESS", "FALLBACK"))]
    if not external:
        return "Connect an external display first. Your layout was not changed."
    if len(external) == 1:
        target = external[0]
    else:
        choice = subprocess.run(["fuzzel", "--dmenu", "--keyboard-focus=exclusive",
                                 "--prompt", "Mirror display: "], input="\n".join(external),
                                text=True, capture_output=True)
        if choice.returncode or choice.stdout.strip() not in external:
            return None
        target = choice.stdout.strip()

    if active[laptop].get("mirrorOf") == target:
        ctl("reload")  # Restore the saved extended layout, including positions and timings.
        extended = lambda a: laptop in a and target in a and not mirror(a[laptop]) and not mirror(a[target])
        try:
            until(extended)
        except RuntimeError:
            a = outputs()
            if laptop not in a or target not in a:
                return "Display disconnected; the saved layout has been reloaded."
            # A saved Mirror profile may itself be active. Override it for this session.
            ctl("eval", rule(a[laptop], position="0x0"))
            ctl("eval", rule(a[target], position="auto-right"))
            until(extended)
        return "Extended displays restored."

    try:
        # The external must stop mirroring before it can become the source.
        ctl("eval", rule(active[target]))
        until(lambda a: target in a and not mirror(a[target]))
        ctl("eval", rule(active[laptop], target))
        until(lambda a: laptop in a and a[laptop].get("mirrorOf") == target)
    except (RuntimeError, subprocess.SubprocessError):
        ctl("reload")
        raise
    return f"Mirroring at {target}’s preferred mode. Press the shortcut again to extend."


if __name__ == "__main__":
    try:
        message = apply()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as err:
        message = f"Display change failed: {err}"
        print(message, file=sys.stderr)
        status = 1
    else:
        status = 0
    if message:
        subprocess.run(["notify-send", "Display layout", message], check=False)
    sys.exit(status)
