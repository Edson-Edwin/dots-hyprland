"""Open Dolphin's action for the file under the pointer or its selected group."""
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import dbus
from dbus.lowlevel import SignalMessage

ACTION="servicemenu_ii-format-wheel.desktop::wheel"

GROUP="servicemenu_ii-group-files.desktop::group"

def hypr(*args):
    return subprocess.check_output(["hyprctl",*args],timeout=2,text=True).strip()
def active():
    return json.loads(hypr("-j","activewindow"))

def main():
    window=active()
    address=window.get("address","")
    if window.get("class","").lower()!="org.kde.dolphin" or not re.fullmatch(r"0x[0-9a-f]+",address):return
    dest=f"org.kde.dolphin-{int(window['pid'])}"
    bus=dbus.SessionBus()
    obj=bus.get_object(dest,"/dolphin",introspect=False)
    nodes=ET.fromstring(obj.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable",timeout=2))
    for child in nodes.findall("node"):
        obj=bus.get_object(dest,"/dolphin/"+child.get("name",""),introspect=False)
        if not obj.isActiveWindow(dbus_interface="org.kde.dolphin.MainWindow",timeout=2):continue
        act=dbus.Interface(obj,"org.kde.KMainWindow")
        if not {ACTION,GROUP}.issubset(act.actions(timeout=2)):
            # Dolphin caches service shortcuts when a window is constructed.
            msg=SignalMessage("/kservicemenurc","org.kde.kconfig.notify","ConfigChanged")
            msg.append({"Show":[dbus.ByteArray(b"ii-format-wheel.desktop")]},signature="a{saay}")
            bus.send_message(msg);bus.flush()
            for _ in range(12):
                if {ACTION,GROUP}.issubset(act.actions(timeout=2)):break
                time.sleep(.05)
            else:raise ValueError("Dolphin did not load Convert / PDF tools.")
        if active().get("address")!=address:return
        # Native context selection keeps a selected group, or selects the
        # pointed-to item if it isn't in the group. Never touch the clipboard.
        def key(name,state):
            hypr("dispatch",'hl.dsp.send_key_state({mods="",key="%s",state="%s",window="address:%s"})' % (name,state,address))
        key("mouse:273","down");key("mouse:273","up")
        time.sleep(.12)
        if active().get("address")!=address:return
        key("Escape","down");key("Escape","up")
        # KIO checks each action's mutually exclusive URL-count rule against the selection.
        for name in (GROUP,ACTION):
            if act.actionIsEnabled(name,timeout=2):act.activateAction(name,timeout=2)
        return
if __name__=="__main__":
    try:main()
    except (OSError,ValueError,subprocess.SubprocessError,dbus.DBusException) as exc:
        subprocess.run(["notify-send","Dolphin file actions",str(exc)[:220]],check=False)
        sys.exit(1)
