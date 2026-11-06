import json,os,sys,tempfile,time
from pathlib import Path
from PySide6.QtCore import QCoreApplication
sys.path.insert(0,str((Path(__file__).resolve().parents[2] / 'dots/.config/hypr/hyprland/scripts/edson/voice-ai')))
from theme import Theme,DEFAULTS
app=QCoreApplication([])
def until(predicate):
 end=time.monotonic()+3
 while not predicate() and time.monotonic()<end:app.processEvents();time.sleep(.01)
 assert predicate(),'Theme event did not apply'
with tempfile.TemporaryDirectory() as directory:
 path=Path(directory)/'generated/colors.json'
 theme=Theme(path=path)
 path.parent.mkdir();colors=dict(DEFAULTS,primary='#123456');path.write_text(json.dumps(colors))
 until(lambda:theme.colors['primary']=='#123456')
 for value in ('#abcdef','#654321'):
  colors['primary']=value;tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(colors));os.replace(tmp,path)
  until(lambda:theme.colors['primary']==value)
 path.write_text('{"primary":')
 until(lambda:theme.timer.isActive())
 until(lambda:not theme.timer.isActive() and theme.retries==5)
 assert theme.colors['primary']=='#654321'
 path.write_text(json.dumps(dict(colors,primary='invalid')))
 until(lambda:theme.timer.isActive())
 until(lambda:not theme.timer.isActive() and theme.retries==5)
 assert theme.colors['primary']=='#654321'
 path.unlink();app.processEvents()
 colors['primary']='#fedcba';path.write_text(json.dumps(colors))
 until(lambda:theme.colors['primary']=='#fedcba')
 theme.stop();assert not theme.watcher.files() and not theme.watcher.directories()
 print('PASS: first palette creation, repeated atomic replacement, incomplete/invalid palette retention, deletion/recreation, bounded retries, watcher cleanup')
