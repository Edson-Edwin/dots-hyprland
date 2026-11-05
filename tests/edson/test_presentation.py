"""Exercise presentation mirroring with synthetic displays, without touching the desktop."""
import runpy,json,re
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
apply=runpy.run_path(str(Path(__file__).resolve().parents[2] / 'dots/.config/hypr/hyprland/scripts/edson/mirror-fit.py'))['apply'];ns=apply.__globals__
for name,mode,refresh in [('HDMI-A-1',(1920,1080),60),('DP-2',(3840,2160),120),('DP-3',(3440,1440),100)]:
 laptop=dict(name='eDP-1',width=1920,height=1200,x=0,y=0,scale=1,transform=0,mirrorOf='none')
 ext={**laptop,'name':name,'width':1280,'height':720,'x':1920}
 saved={m['name']:m for m in (laptop,ext)}
 a=deepcopy(saved)
 def ctl(*cmd):
  if cmd==('reload',):
   a.clear();a.update(deepcopy(saved));return
  n=json.loads(re.search(r'output=("[^"]+")',cmd[1])[1])
  target=json.loads(re.search(r'mirror=("[^"]*")',cmd[1])[1])
  assert 'mode="preferred"' in cmd[1]
  a[n]['mirrorOf']=target or 'none'
  if n==name:
   assert 'position="auto-right"' in cmd[1]
   a[n].update(width=mode[0],height=mode[1],refreshRate=refresh,x=1920)
 moved=[];placements={1:"eDP-1",2:"eDP-1",6:name}
 def fake(*cmd):
  if cmd==("-j","workspaces"):
   return json.dumps([dict(id=i,monitor=m,windows=1) for i,m in placements.items()])
  if cmd[0]=="dispatch":
   if "workspace.move" in cmd[1]:
    i=int(re.search(r"workspace=(\d+)",cmd[1])[1]);placements[i]="eDP-1";moved.append(i)
   return "ok"
  return ctl(*cmd)
 import tempfile,os
 with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,XDG_RUNTIME_DIR=td),patch.dict(ns,outputs=lambda:deepcopy(a),ctl=fake):
  a.pop(name);assert "not changed" in apply()
  a[name]=deepcopy(ext)
  assert apply(True,name) is None and a["eDP-1"]["mirrorOf"]=="none"
  assert f"{mode[0]}×{mode[1]}" in apply()
  placements.update({1:name,2:name})
  assert "Extended" in apply() and a[name]["x"]==1920
  assert sorted(moved)==[1,2] and placements[6]==name
print("PASS: no mirroring on connect/login, manual presentation at preferred mode, non-overlapping placement and laptop workspace restoration")
