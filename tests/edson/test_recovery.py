import os,tempfile,sys,importlib.machinery,types,shutil
from pathlib import Path
src=Path(__file__).with_name('ii-desktop-recovery')
if not src.exists():src=Path(__file__).resolve().parents[2]/'dots/.local/bin/ii-desktop-recovery'
with tempfile.TemporaryDirectory() as td:
 d=Path(td);os.environ.update(HOME=td,XDG_CONFIG_HOME=str(d/'cfg'),XDG_STATE_HOME=str(d/'state'),XDG_DATA_HOME=str(d/'data'))
 mod=types.ModuleType('recover');exec(compile(src.read_bytes(),str(src),'exec'),mod.__dict__)
 mod.health=lambda:None;mod.stop=lambda:None;mod.start=lambda:None;mod.run=lambda *a,**k:None;mod.validate=lambda:None
 hy=mod.CONFIG/'hypr/hyprland.lua';hy.parent.mkdir(parents=True);hy.write_text('baseline')
 shell=mod.CONFIG/'quickshell/ii/shell.qml';shell.parent.mkdir(parents=True);shell.write_text('panel')
 link=shell.parent/'testlink';link.symlink_to('shell.qml')
 backup=mod.snapshot('working');assert backup.stat().st_mode & 0o777==0o600
 hy.write_text('changed');extra=hy.parent/'extra';extra.touch();mod.restore(backup)
 assert hy.read_text()=='baseline' and not extra.exists() and link.is_symlink()
 shell.unlink();mod.restore(backup);assert shell.read_text()=='panel'
 hy.write_text('user edit')
 def fail():raise RuntimeError("invalid restored config")
 mod.validate=fail
 try:mod.restore(backup)
 except RuntimeError as e:assert 'previous files put back' in str(e)
 else:raise AssertionError
 assert hy.read_text()=='user edit'
 with backup.open('ab') as f:f.write(b'x')
 try:mod.restore(backup)
 except ValueError as e:assert 'checksum' in str(e)
 else:raise AssertionError
 assert hy.read_text()=='user edit'
 print("PASS: private backup, actual restore of files and symlink, failure rollback and corrupt archive rejection (isolated config)")
