#!/usr/bin/env python3
"""Toggle an edge-to-edge presentation on an external display. Never run on hot-plug."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECTOR = Path(__file__).resolve().with_name("projector")

def ctl(*args):
    p = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=5)
    if p.returncode or (args[0] in ("eval","dispatch") and "error" in p.stdout.lower()):
        raise RuntimeError((p.stderr or p.stdout).strip() or "Hyprland rejected the request.")
    return p.stdout

def outputs():
    return {m["name"]:m for m in json.loads(ctl("-j","monitors","all"))
            if not m.get("disabled") and m["width"]>0}

def qs(*args, env=None):
    return subprocess.run(["qs","-p",str(PROJECTOR),*args],capture_output=True,text=True,timeout=8,env=env)

def call(method):
    return qs("ipc","call","projector",method)

def stop():
    if call("stop").returncode:
        qs("kill")  # Only this projection instance, never the desktop shell.
    for _ in range(20):
        if call("status").returncode:return
        time.sleep(.1)
    raise RuntimeError("The presentation window did not close.")

def independent(m,pos):
    opts={"output":m["name"],"mode":"preferred","position":pos,"scale":m["scale"],
          "transform":m["transform"],"mirror":""}
    return "hl.monitor({"+",".join(f"{k}={json.dumps(v)}" for k,v in opts.items())+"})"

def prepare(laptop,target):
    source,external=laptop["name"],target["name"]
    if laptop.get("mirrorOf")==external or target.get("mirrorOf")==source:
        # A native clone cannot host a separate fullscreen surface. Replace
        # only this explicitly chosen pair with non-overlapping outputs.
        inherited=target.get("activeWorkspace",{}).get("id") if laptop.get("mirrorOf")==external else None
        ctl("eval",independent(target,"auto-right")+";"+independent(laptop,"0x0"))
        for _ in range(25):
            ms=outputs()
            if all(ms.get(n,{}).get("mirrorOf")=="none" for n in (source,external)):break
            time.sleep(.1)
        else:raise RuntimeError("Could not separate the native mirror. Apply the extended layout first.")
        if inherited and inherited>0:
            ctl("dispatch",f"hl.dsp.workspace.move({{workspace={inherited},monitor={json.dumps(source)}}})")
    elif any(m.get("mirrorOf") not in (None,"none","") for m in (laptop,target)):
        raise RuntimeError("Extend these displays before presenting; one is mirroring another output.")

def apply(auto=False):
    if auto:return None
    if call("status").returncode==0:
        stop();return "Presentation stopped. Both displays are independent."
    ms=outputs()
    laptop=next((k for k in ms if k.startswith(("eDP","LVDS","DSI"))),None)
    if laptop is None:return "No active laptop display."
    external=[k for k in ms if k!=laptop and not k.startswith(("HEADLESS","FALLBACK"))]
    if not external:return "Connect an external display first. Your layout was not changed."
    if len(external)==1:target=external[0]
    else:
        p=subprocess.run(["fuzzel","--dmenu","--keyboard-focus=exclusive","--prompt","Present on: "],
                         input="\n".join(external),text=True,capture_output=True)
        target=p.stdout.strip()
        if p.returncode or target not in external:return None
    prepare(ms[laptop],ms[target])
    ctl("dispatch","hl.dsp.focus({monitor="+json.dumps(laptop)+"})")
    started=qs("-n","-d",env={**os.environ,"II_PRESENT_FROM":laptop,"II_PRESENT_TO":target})
    if started.returncode:raise RuntimeError(started.stderr.strip() or "Projector failed to start.")
    for _ in range(40):
        if call("status").stdout.strip()=="ready":
            return f"Presenting the entire laptop screen on {target}. Super+Alt+P stops."
        time.sleep(.15)
    qs("kill")
    raise RuntimeError("Couldn't capture the laptop screen. The projection has been closed.")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auto",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("connector",nargs="?",help=argparse.SUPPRESS)
    args=parser.parse_args()
    try:
        with (Path(os.environ["XDG_RUNTIME_DIR"])/"edson-display-layout.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            message=apply(args.auto)
        status=0
    except (ValueError,OSError,RuntimeError,subprocess.SubprocessError) as e:
        message=f"Presentation failed: {e}";status=1
    if message:subprocess.run(["notify-send","Display layout",message],check=False)
    sys.exit(status)
