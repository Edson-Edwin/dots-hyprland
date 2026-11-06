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
   assert 'position="0x0"' in cmd[1]
   a[n].update(width=mode[0],height=mode[1],refreshRate=refresh,x=0)
 with patch.dict(ns,outputs=lambda:deepcopy(a),ctl=ctl):
  a.pop(name);assert apply(True,name)==None
  a[name]=deepcopy(ext)
  for port in [name,None,name]:
   assert f'{mode[0]}×{mode[1]}' in apply(True,port)
   assert a['eDP-1']['mirrorOf']==name and a[name]['mirrorOf']=='none'
  assert 'Extended' in apply() and a[name]['x']==1920 and a['eDP-1']['mirrorOf']=='none'
  a['DP-6']={**ext,'name':'DP-6'};assert apply(True)==None
print('PASS: connect, login, repeated event, disconnect/no target, preferred timings and origin, extend, multi-screen startup')
