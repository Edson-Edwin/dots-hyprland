"""Check presentation lifecycle without modifying a real desktop."""
import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
g=runpy.run_path(str(Path(__file__).resolve().parents[2]/'dots/.config/hypr/hyprland/scripts/edson/mirror-fit.py'))['apply'].__globals__
apply=g['apply']
ms={n:dict(name=n,mirrorOf="none",scale=1,transform=0) for n in ['eDP-1','HDMI-A-1']}
live=False;calls=[]
def result(rc=0,out=''):return SimpleNamespace(returncode=rc,stdout=out,stderr='')
def call(name):
    global live
    if name=='stop':live=False;return result()
    return result(0 if live else 1,'ready' if live else '')
def qs(*args,env=None):
    global live
    assert args==('-n','-d') and env['II_PRESENT_FROM']=='eDP-1' and env['II_PRESENT_TO']=='HDMI-A-1'
    live=True;return result()
with patch.dict(g,outputs=lambda:ms,call=call,qs=qs,ctl=lambda *args:calls.append(args)):
    assert apply(True) is None and not calls
    assert 'Presenting' in apply() and live
    assert calls==[('dispatch','hl.dsp.focus({monitor="eDP-1"})')]
    assert 'stopped' in apply() and not live and len(calls)==1
    del ms['HDMI-A-1']
    assert 'not changed' in apply()
print('PASS: no hot-plug changes, source/target selection, no workspace or mode changes in extended layout, clean stop and no-target fallback')
