"""Ask the active Dolphin window to open its native single-file service action."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
import dbus

ACTION="servicemenu_ii-format-wheel.desktop::wheel"
def main():
    active=json.loads(subprocess.check_output(["hyprctl","-j","activewindow"],timeout=2))
    if active.get("class","").lower()!="org.kde.dolphin":return
    dest=f"org.kde.dolphin-{int(active['pid'])}"
    bus=dbus.SessionBus()
    base=bus.get_object(dest,"/dolphin",introspect=False)
    nodes=ET.fromstring(base.Introspect(dbus_interface="org.freedesktop.DBus.Introspectable",timeout=2))
    for child in nodes.findall("node"):
        path="/dolphin/"+child.get("name","")
        obj=bus.get_object(dest,path,introspect=False)
        if not obj.isActiveWindow(dbus_interface="org.kde.dolphin.MainWindow",timeout=2):continue
        act=dbus.Interface(obj,"org.kde.KMainWindow")
        if act.actionIsEnabled(ACTION,timeout=2):act.activateAction(ACTION,timeout=2)
        return
if __name__=="__main__":
    try:main()
    except (OSError, ValueError, subprocess.SubprocessError, dbus.DBusException) as e:
        sys.exit(str(e))
