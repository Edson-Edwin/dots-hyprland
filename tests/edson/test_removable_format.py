"""Synthetic block inventory only. Never start Disks or format a real device."""
from pathlib import Path
import os, runpy, stat
from types import SimpleNamespace
src=Path(__file__).resolve().parents[2]/"dots/.config/quickshell/ii/scripts/removable/format_drive.py"
mod=runpy.run_path(str(src));candidates=mod['candidates'];launch=mod['launch']
def disk(name="sdb",**props):
    return dict({"type":"disk","path":"/dev/"+name,"name":name,"maj:min":"8:16","size":10**9,
                 "tran":"usb","ro":False,"mountpoints":[None]},**props)
def part(i,**props):
    return dict({"type":"part","path":"/dev/sdb"+str(i),"name":"sdb"+str(i),"maj:min":"8:"+str(16+i),
                 "size":9*10**8,"pttype":"gpt","ro":False,"fstype":"exfat","mountpoints":["/run/media/test/CARD"]},**props)
def attrs(n,k):return "12" if k=="diskseq" else ("SD" if n=='mmcblk1' else "MMC")
valid=candidates([disk(children=[part(1),part(2)])],attrs)
assert [v.path for v in valid]==["/dev/sdb1","/dev/sdb2"]
assert candidates([disk()],attrs)[0].path=="/dev/sdb"
assert candidates([disk("mmcblk1",tran=None)],attrs)
bad=[disk("nvme0n1",tran="nvme"),disk("mmcblk0",tran=None),disk(ro=True),disk(size=0),
     disk(pttype="gpt"),disk(children=[part(1,mountpoints=["/"]),part(2)]),
     disk(children=[part(1,mountpoints=["/home"]),part(2)]),disk(children=[part(1,fstype="swap")]),
     disk(children=[part(1,fstype="crypto_LUKS")]),disk(children=[part(1,children=[disk("dm-0")])]),
     disk(children=[part(1,parttype="c12a7328-f81f-11d2-ba4b-00a0c93ec93b")])]
assert not candidates(bad,attrs)
assert not candidates([disk()],lambda *_:"")
v=valid[0]; started=[]
st=lambda path: SimpleNamespace(st_mode=stat.S_IFBLK,st_rdev=os.makedev(8,17))
def start(cmd,**kwargs):started.append(cmd)
launch(v,lambda:valid,start,st)
assert started==[['gnome-disks','--block-device','/dev/sdb1','--format-device']]
for inv,stfn in [(lambda:[],st),(lambda:candidates([disk(children=[part(1)])],lambda *_:"15"),st),
                 (lambda:valid,lambda p:SimpleNamespace(st_mode=stat.S_IFREG,st_rdev=0))]:
    try:launch(v,inv,start,stfn)
    except ValueError:pass
    else:raise AssertionError("Unsafe wizard launch")
assert len(started)==1
print("PASS: USB/SD eligibility, volume scope, system/locked/read-only exclusions and device replacement guard")

# The Dolphin action must bind the originally clicked volume, never substitute another.
token=mod['fingerprint'](v)
assert mod['selected_volume'](v.path,token,valid)==v
for target,cookie,choices in [(v.path,"",valid),(valid[1].path,token,valid),(v.path,token,[])]:
    try:mod['selected_volume'](target,cookie,choices)
    except ValueError:pass
    else:raise AssertionError("Substituted or missing volume accepted")
print("PASS: Places action validates the device path and incarnation token")

launch(v,lambda:valid,start,st,inspect=True)
assert started[-1] == ["gnome-disks", "--block-device", v.path]
print("PASS: inspecting a volume opens its details without starting the format dialog")

empty_disk = disk(pttype="dos")
assert not candidates([empty_disk], attrs)
blank, = candidates([empty_disk], attrs, include_empty_tables=True)
assert blank.empty_table and blank.path == "/dev/sdb"
assert not candidates([disk("nvme0n1", tran="nvme", pttype="gpt")], attrs, include_empty_tables=True)
assert not candidates([disk(pttype="gpt", mountpoints=["/"])], attrs, include_empty_tables=True)
whole_stat = lambda _: SimpleNamespace(st_mode=stat.S_IFBLK, st_rdev=os.makedev(8,16))
launch(blank, lambda: [blank], start, whole_stat, inspect=True)
assert started[-1] == ["gnome-disks", "--block-device", blank.path]
try:
    launch(blank, lambda: [blank], start, whole_stat)
except ValueError:
    pass
else:
    raise AssertionError("Empty partition table offered as a formattable volume")
print("PASS: empty USB partition table can be inspected, never formatted as a volume")
