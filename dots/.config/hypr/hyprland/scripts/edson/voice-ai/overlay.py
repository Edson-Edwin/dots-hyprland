"""Event-driven Hyprland overlay; no polling, focus grab, or AI access."""
import os
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, QTimer
from PySide6.QtNetwork import QLocalSocket


class Overlay(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.follow_workspaces = False
        self.enabled = bool(os.environ.get('WAYLAND_DISPLAY') and os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'))
        self.process = QProcess(self)
        self.process.setStandardOutputFile(QProcess.nullDevice())
        self.process.setStandardErrorFile(QProcess.nullDevice())
        self.resize_process = QProcess(self)
        self.resize_process.setStandardOutputFile(QProcess.nullDevice())
        self.resize_process.setStandardErrorFile(QProcess.nullDevice())
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(60)
        self.resize_timer.timeout.connect(self.apply_size)
        self.requested_size = (680,180)
        self.raise_timer = QTimer(self)
        self.raise_timer.setSingleShot(True)
        self.raise_timer.setInterval(80)
        self.raise_timer.timeout.connect(self.raise_window)
        self.events = QLocalSocket(self)
        self.events.readyRead.connect(self.read_events)
        self.events.errorOccurred.connect(lambda _: None)
        if self.enabled:
            path = Path(os.environ['XDG_RUNTIME_DIR'])/'hypr'/os.environ['HYPRLAND_INSTANCE_SIGNATURE']/'.socket2.sock'
            self.events.connectToServer(str(path))

    def read_events(self):
        # Hyprland bounds event lines; discard incomplete oversized input.
        if self.events.bytesAvailable() > 65536:
            self.events.readAll()
            return
        while self.events.canReadLine():
            line = bytes(self.events.readLine()).decode(errors='replace')
            event, _, payload = line.partition('>>')
            if event == 'workspacev2' and self.window.isVisible() and not self.follow_workspaces:
                self.window.close()
            elif event in ('activewindowv2', 'openwindow', 'fullscreen') and self.window.isVisible():
                # A pinned surface already renders above ordinary/fullscreen windows.
                # Raise only on relevant events, without changing keyboard focus.
                if not self.raise_timer.isActive():self.raise_timer.start()

    def raise_window(self):
        if not self.enabled or not self.window.isVisible():return
        if self.process.state() != QProcess.ProcessState.NotRunning:return
        self.process.start('hyprctl', ['dispatch', f'hl.dsp.window.alter_zorder({{mode="top",window="pid:{os.getpid()}"}})' ])

    def shown(self):
        if self.enabled:self.raise_timer.start()

    def resize(self,width,height):
        self.requested_size=(width,height)
        if self.enabled:self.resize_timer.start()

    def apply_size(self):
        if not self.enabled or not self.window.isVisible():return
        if self.resize_process.state()!=QProcess.ProcessState.NotRunning:
            self.resize_timer.start();return
        width,height=self.requested_size
        self.resize_process.start('hyprctl',['dispatch',f'hl.dsp.window.resize({{x={width},y={height},window="pid:{os.getpid()}"}})' ])

    def stop(self):
        self.raise_timer.stop()
        self.resize_timer.stop()
        self.events.abort()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(500)
        if self.resize_process.state()!=QProcess.ProcessState.NotRunning:
            self.resize_process.kill()
            self.resize_process.waitForFinished(500)
