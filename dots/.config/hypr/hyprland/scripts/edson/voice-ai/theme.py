"""Follow Illogical Impulse's generated palette without polling."""
import json
import re
from pathlib import Path
from PySide6.QtCore import QObject,Signal,QTimer,QFileSystemWatcher

DEFAULTS={'surface':'#151515','surface_container':'#242424','on_surface':'#eeeeee',
          'primary':'#a7c080','on_surface_variant':'#bbbbbb','outline_variant':'#454545',
          'on_primary':'#151515'}


class Theme(QObject):
    changed=Signal()
    def __init__(self,parent=None,path=None):
        super().__init__(parent)
        self.path=Path(path) if path else Path.home()/'.local/state/quickshell/user/generated/colors.json'
        self.colors=dict(DEFAULTS)
        self.retries=0
        self.watcher=QFileSystemWatcher(self)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(150)
        self.timer.timeout.connect(self.reload)
        self.watcher.fileChanged.connect(self.schedule)
        self.watcher.directoryChanged.connect(self.schedule)
        self.reload()

    def schedule(self,*_):
        self.retries=0;self.timer.start()

    def watch_paths(self):
        # A file watch is removed by atomic replacement. The parent watch lets
        # us reattach; the nearest existing ancestor also covers first creation.
        parent=self.path.parent
        while not parent.exists() and parent!=parent.parent:parent=parent.parent
        wanted={str(parent)}
        if self.path.exists():wanted.add(str(self.path))
        current=set(self.watcher.files()+self.watcher.directories())
        if current-wanted:self.watcher.removePaths(list(current-wanted))
        if wanted-current:self.watcher.addPaths(list(wanted-current))

    def reload(self):
        self.watch_paths()
        try:
            with self.path.open() as source:data=json.loads(source.read(65537))
            if not isinstance(data,dict):raise ValueError('Invalid palette')
            colors={key:data.get(key,data.get('surface') if key=='on_primary' else None) for key in DEFAULTS}
            if not all(isinstance(value,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',value) for value in colors.values()):raise ValueError('Incomplete palette')
        except (OSError,ValueError):
            # Keep the last good theme while the generator is writing.
            if self.retries<5:self.retries+=1;self.timer.start()
            return
        self.retries=0
        if colors!=self.colors:self.colors=colors;self.changed.emit()

    def stop(self):
        self.timer.stop()
        paths=self.watcher.files()+self.watcher.directories()
        if paths:self.watcher.removePaths(paths)
