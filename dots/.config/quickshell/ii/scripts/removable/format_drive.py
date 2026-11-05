#!/usr/bin/env python3
"""Offer the system's interactive format wizard for eligible removable volumes."""
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


@dataclass(frozen=True)
class Volume:
    path: str
    devno: str
    seq: str
    uuid: str
    partuuid: str
    size: int
    model: str
    label: str
    fs: str

    def title(self):
        return f"{self.model} · {self.size/2**30:.1f} GiB · {self.label or 'Unlabelled'} ({self.fs or 'unformatted'}) · {self.path}"


def sysattr(name, key):
    try:
        return (Path("/sys/class/block") / name / key).read_text().strip()
    except OSError:
        return ""


def candidates(disks, attr=sysattr):
    result = []
    # Do not offer system, active layered, encrypted, or swap devices.
    unsafe_fs = {"swap","crypto_luks","lvm2_member","linux_raid_member","zfs_member","iso9660","udf","btrfs"}
    boot_types = {"c12a7328-f81f-11d2-ba4b-00a0c93ec93b", "21686148-6449-6e6f-744e-656564454649", "0xef"}
    for disk in disks:
        name = disk["name"]
        if disk["type"] != "disk" or disk["ro"] or not disk["size"]: continue
        if disk.get("tran") != "usb" and attr(name, "device/type") != "SD": continue
        seq = attr(name, "diskseq")
        if not seq.isdecimal(): continue
        parts = disk.get("children", [])
        nodes = [disk, *parts]
        if any(p.get("children") for p in parts): continue
        if any(str(p.get("fstype") or "").lower() in unsafe_fs for p in nodes): continue
        mounts = [m for p in nodes for m in (p.get("mountpoints") or []) if m]
        if any(not any(m.startswith(prefix) for prefix in ("/run/media/","/media/","/mnt/")) for m in mounts): continue
        if not parts and disk.get("pttype"): continue
        for p in parts or [disk]:
            if p["ro"] or not p["size"] or (p is not disk and p["type"]!="part"): continue
            if str(p.get("parttype") or "").lower() in boot_types|{"0x5","0xf","0x85"}: continue
            result.append(Volume(p["path"],p["maj:min"],seq,p.get("uuid") or "",p.get("partuuid") or "",
                p["size"],(disk.get("model") or name).strip(),p.get("label") or "",p.get("fstype") or ""))
    return result


def scan():
    cols="NAME,PATH,TYPE,MAJ:MIN,TRAN,RM,RO,SIZE,MODEL,LABEL,FSTYPE,MOUNTPOINTS,PTTYPE,PARTTYPE,UUID,PARTUUID"
    p=subprocess.run(["lsblk","-J","-b","-o",cols],capture_output=True,text=True,check=True,timeout=6)
    return candidates(json.loads(p.stdout)["blockdevices"])


def launch(volume, inventory=scan, start=subprocess.Popen, stat_fn=os.stat):
    # Revalidate the same disk incarnation, volume and kernel device number
    # after any selection dialog. No mkfs/format command runs in this helper.
    if volume not in inventory(): raise ValueError("That drive changed or was removed. Open the chooser again.")
    st=stat_fn(volume.path)
    if not stat.S_ISBLK(st.st_mode) or f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}"!=volume.devno:
        raise ValueError("The selected device is no longer available.")
    start(["gnome-disks","--block-device",volume.path,"--format-device"],start_new_session=True)


def watch():
    # Subscribe only while the sidebar is open. Debounce UDisks hot-plug events.
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus=dbus.SystemBus()
    pending=0
    def report():
        nonlocal pending
        pending=0
        try: print("1" if scan() else "0",flush=True)
        except (OSError,ValueError,subprocess.SubprocessError): print("0",flush=True)
        return False
    def changed(*_):
        nonlocal pending
        if not pending:pending=GLib.timeout_add(350,report)
    for interface,signal in (("org.freedesktop.DBus.ObjectManager","InterfacesAdded"),
                             ("org.freedesktop.DBus.ObjectManager","InterfacesRemoved"),
                             ("org.freedesktop.DBus.Properties","PropertiesChanged")):
        bus.add_signal_receiver(changed,bus_name="org.freedesktop.UDisks2",dbus_interface=interface,signal_name=signal)
    report();GLib.MainLoop().run()


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--watch",action="store_true")
    arg.add_argument("--list",action="store_true")
    a=arg.parse_args()
    if a.watch:watch();return
    choices=scan()
    if a.list:
        for v in choices:print(v.title())
        return
    if not choices:
        subprocess.run(["kdialog","--msgbox","No eligible USB or SD volume is connected."]);return
    if len(choices)==1:v=choices[0]
    else:
        p=subprocess.run(["kdialog","--title","Format removable storage","--menu","Choose the volume to format",
                          *[item for v in choices for item in (v.path,v.title())]],capture_output=True,text=True)
        if p.returncode:return
        v=next(v for v in choices if v.path==p.stdout.strip())
    launch(v)

if __name__=="__main__":
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        if "--watch" not in sys.argv and "--list" not in sys.argv:
            subprocess.run(["kdialog","--error",str(e)])
        sys.exit(1)
