#!/usr/bin/env python3
"""On-demand voice typing and text-only AI chat for Hyprland."""
import atexit
import fcntl
import html
import json
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import threading
import time

os.umask(0o077)
RUNTIME=Path(os.environ.get('XDG_RUNTIME_DIR',f'/run/user/{os.getuid()}'))/'ii-voice-ai'
RUNTIME.mkdir(mode=0o700,parents=True,exist_ok=True)
STATUS=RUNTIME/'status.json'
SOCKET=str(RUNTIME/'control.sock')
ACTION=sys.argv[1] if len(sys.argv)>1 else 'menu'
if ACTION=='init':
    alive=False
    try:
        pid=json.loads(STATUS.read_text()).get('pid',0)
        if pid>0:os.kill(pid,0);alive=True
    except (OSError,ValueError,TypeError):pass
    if not alive:STATUS.write_text('{"state":"idle"}')
    sys.exit(0)
if ACTION not in ['menu','settings','chat','dictate','cancel','quit']:
    raise SystemExit('Unknown action')
# Resolve a running instance before importing Qt. The lock also prevents startup races.
lock=open(RUNTIME/'instance.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:
    for _ in range(40):
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(.3);client.connect(SOCKET);client.sendall((ACTION+'\n').encode())
            sys.exit(0)
        except OSError:time.sleep(.05)
    raise SystemExit('Voice & Chat is starting. Try again shortly.')

# Match the working Quickshell bridge without affecting other desktop apps.
os.environ['QT_QPA_PLATFORM']='wayland' if os.environ.get('WAYLAND_DISPLAY') else os.environ.get('QT_QPA_PLATFORM','offscreen')
if os.environ.get('WAYLAND_DISPLAY'):
    os.environ['QT_QPA_PLATFORMTHEME']='gtk3'
    os.environ['QT_WAYLAND_SHELL_INTEGRATION']='xdg-shell'
else:os.environ.pop('QT_QPA_PLATFORMTHEME',None)
os.environ['QT_STYLE_OVERRIDE']='Fusion'
from PySide6.QtCore import QObject,Signal,QTimer,QProcess,Qt,QSize,QRectF
from PySide6.QtGui import QFont,QTextCursor,QKeySequence,QShortcut,QColor,QIcon,QPainter,QPalette
from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTabWidget,
    QTextBrowser,QPlainTextEdit,QLineEdit,QComboBox,QFormLayout,QGroupBox,QCheckBox,QScrollArea,QLayout)
from PySide6.QtNetwork import QLocalServer
import backend as api
from overlay import Overlay
from theme import Theme

class Events(QObject):
    finished=Signal(int,object,str)

class ChatInput(QPlainTextEdit):
    sendRequested=Signal()
    def __init__(self):
        super().__init__();self.composing=False
    def inputMethodEvent(self,event):
        self.composing=bool(event.preeditString())
        super().inputMethodEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and not self.composing:
            modifiers=event.modifiers()
            if modifiers in (Qt.KeyboardModifier.NoModifier,Qt.KeyboardModifier.ControlModifier):
                if not event.isAutoRepeat():self.sendRequested.emit()
                event.accept();return
        super().keyPressEvent(event)

class DragHeading(QLabel):
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove();event.accept()
        else:super().mousePressEvent(event)

class Window(QWidget):
    def __init__(self,controller):
        super().__init__();self.controller=controller
        self.setWindowTitle('Voice & Chat');self.resize(680,180);self.chat_mode=False;self.glass_tint=QColor(255,255,255,12)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint,True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName('overlay')
        outer=QVBoxLayout(self);outer.setContentsMargins(12,12,12,12);outer.setSpacing(10)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        header=QWidget();header.setObjectName('header');top=QHBoxLayout(header)
        heading=DragHeading('Voice & Chat');self.heading=heading;heading.setObjectName('heading');heading.setToolTip('Drag to move · Super + right-drag to resize');top.addWidget(heading,1)
        self.pin=QPushButton();self.pin.setFixedSize(42,42);self.pin.setStyleSheet('padding:8px;');self.pin.setIconSize(QSize(24,24));self.pin.setCheckable(True);self.pin.setToolTip('Keep this overlay visible when switching workspaces (Alt + P)');self.pin.setAccessibleName('Pin across workspaces');top.addWidget(self.pin)
        close=QPushButton('×');close.setFixedWidth(42);close.setToolTip('Hide (Escape)');close.setAccessibleName('Hide Voice & Chat');close.clicked.connect(self.close);top.addWidget(close)
        outer.addWidget(header)
        self.tabs=QTabWidget();outer.addWidget(self.tabs)
        voice=QWidget();voice.setObjectName('panel');v=QVBoxLayout(voice);v.setSpacing(16)
        self.voice_state=QLabel('Ready to listen');self.voice_state.setObjectName('heading');v.addWidget(self.voice_state)
        description=QLabel('Focus a text field, then press Ctrl + Super + D.\nPress it again to stop and transcribe.\n\nAudio goes only to your selected transcription provider.\nEach recording is limited to two minutes.');description.setWordWrap(True);v.addWidget(description)
        self.record=QPushButton('Start dictation');self.record.clicked.connect(controller.toggle_dictation);v.addWidget(self.record)
        cancel=QPushButton('Cancel recording / transcription');cancel.clicked.connect(controller.cancel);v.addWidget(cancel)
        v.addWidget(QLabel('Last transcript'))
        self.transcript=QPlainTextEdit();self.transcript.setReadOnly(True);self.transcript.setPlaceholderText('Your latest transcript appears here.');v.addWidget(self.transcript)
        copy=QPushButton('Copy transcript');copy.clicked.connect(lambda:QApplication.clipboard().setText(self.transcript.toPlainText()));v.addWidget(copy)
        self.tabs.addTab(voice,'Voice')
        chat=QWidget();c=QVBoxLayout(chat);c.setContentsMargins(0,0,0,0)
        self.history=QTextBrowser();self.history.setObjectName('conversation');self.history.setOpenExternalLinks(False);self.history.setOpenLinks(False);self.history.viewport().setAutoFillBackground(False);c.addWidget(self.history,1);self.history.hide()
        composer=QWidget();self.composer=composer;composer.setObjectName('composer');composer.setFixedHeight(54);row=QHBoxLayout(composer);row.setContentsMargins(6,4,6,4);row.setSpacing(4)
        self.clear=QPushButton('＋');self.clear.setToolTip('New chat');self.clear.setAccessibleName('New chat');self.clear.clicked.connect(controller.new_chat);row.addWidget(self.clear)
        self.input=ChatInput();self.input.setObjectName('prompt');self.input.setFixedHeight(46);self.input.setPlaceholderText('Ask anything…');self.input.setToolTip('Enter to send · Shift + Enter for a new line');self.input.sendRequested.connect(controller.send_chat);self.input.textChanged.connect(self.fit_prompt);row.addWidget(self.input,1)
        self.stop=QPushButton('■');self.stop.setToolTip('Stop response');self.stop.setAccessibleName('Stop response');self.stop.clicked.connect(controller.cancel);row.addWidget(self.stop)
        self.send=QPushButton('↑');self.send.setObjectName('send');self.send.setToolTip('Send (Enter)');self.send.setAccessibleName('Send message');self.send.clicked.connect(controller.send_chat);row.addWidget(self.send)
        for button in (self.clear,self.stop,self.send):button.setFixedSize(38,38);button.setStyleSheet('padding:0;font-size:22px;')
        c.addWidget(composer)
        self.tabs.addTab(chat,'Chat')
        settings=QWidget();settings.setObjectName('panel');s=QVBoxLayout(settings)
        info=QLabel('Choose a provider separately for voice and chat. API keys are stored in your desktop keyring.\nCustom services must support the selected API format. Provider usage charges may apply.');info.setWordWrap(True);s.addWidget(info)
        self.fields={}
        config=controller.config
        for slot,label in [('transcription','Voice transcription'),('chat','AI chat')]:
            box=QGroupBox(label);form=QFormLayout(box);fields={}
            preset=QComboBox();preset.addItems(['Keep current / Custom','OpenAI','Groq','Google Gemini']+(['Anthropic'] if slot=='chat' else []));form.addRow('Provider',preset)
            fmt=QComboBox();fmt.addItem('OpenAI-compatible','openai');fmt.addItem('Google Gemini','gemini')
            if slot=='chat':fmt.addItem('Anthropic Messages','anthropic')
            fmt.setCurrentIndex(max(0,fmt.findData(config[slot]['format'])));fields['format']=fmt;form.addRow('API format',fmt)
            for key,title in [('base_url','API base URL'),('model','Model ID')]:
                line=QLineEdit(config[slot][key]);fields[key]=line;form.addRow(title,line)
            key=QLineEdit();key.setEchoMode(QLineEdit.EchoMode.Password);key.setPlaceholderText('Enter a key; leave blank to keep this endpoint’s saved key');fields['key']=key;form.addRow('API key',key)
            forget=QCheckBox('Remove saved key for this endpoint');fields['forget']=forget;form.addRow('',forget)
            self.fields[slot]=fields
            preset.currentTextChanged.connect(lambda name,slot=slot:self.preset(slot,name))
            s.addWidget(box)
        form=QFormLayout();self.language=QLineEdit(config.get('language',''));self.language.setPlaceholderText('Automatic, or language code such as en, ml, hi');form.addRow('Speech language',self.language);s.addLayout(form)
        self.auto_paste=QCheckBox('Paste into the original window after transcription');self.auto_paste.setChecked(config.get('auto_paste',True));s.addWidget(self.auto_paste)
        self.save=QPushButton('Save settings');self.save.clicked.connect(controller.save_settings);s.addWidget(self.save)
        s.addStretch()
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(settings);self.tabs.addTab(scroll,'Settings')
        self.message=QLabel('');self.message.setWordWrap(True);self.message.setObjectName('muted');outer.addWidget(self.message)
        self.message.hide()
        self.escape=QShortcut(QKeySequence('Escape'),self);self.escape.activated.connect(self.close)
        self.overlay=Overlay(self)
        self.pin.toggled.connect(self.set_pinned)
        self.pin_shortcut=QShortcut(QKeySequence('Alt+P'),self);self.pin_shortcut.activated.connect(self.pin.toggle)
        self.tabs.currentChanged.connect(self.set_page)
    def paintEvent(self,event):
        if self.chat_mode:
            # A nearly clear surface gives Hyprland a blur region, without a dark panel.
            painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(self.glass_tint)
            painter.drawRoundedRect(QRectF(self.rect()),20,20)
        else:super().paintEvent(event)
    def set_page(self,index):
        self.chat_mode=index==1;self.tabs.tabBar().setVisible(not self.chat_mode)
        self.heading.setText('Chat' if self.chat_mode else 'Voice & Chat')
        self.setProperty('chatMode',self.chat_mode)
        self.setMinimumSize(360,160 if self.chat_mode else 650)
        self.controller.style();self.update()
        self.resize_overlay(680,500 if self.chat_mode and not self.history.isHidden() else 180 if self.chat_mode else 700)
    def resize_overlay(self,width,height):
        self.resize(width,height)
        self.overlay.resize(width,height)
    def fit_prompt(self):
        lines=min(4,self.input.toPlainText().count('\n')+1)
        self.input.setFixedHeight(46+(lines-1)*self.input.fontMetrics().lineSpacing())
        self.composer.setFixedHeight(self.input.height()+8)
        if self.chat_mode and self.history.isHidden():self.resize_overlay(self.width(),180+(lines-1)*self.input.fontMetrics().lineSpacing())
    def show_conversation(self):
        self.history.show()
        if self.chat_mode:self.resize_overlay(self.width(),max(500,self.height()))
    def set_pinned(self,pinned):
        self.overlay.follow_workspaces=pinned
        self.pin.setToolTip('Visible across workspaces — click to unpin' if pinned else 'Keep visible when switching workspaces')
        self.controller.style()
    def update_pin_icon(self,color):
        icon=QIcon('/usr/share/icons/breeze/actions/24/window-pin.svg')
        if icon.isNull():icon=QIcon.fromTheme('window-pin')
        pixmap=icon.pixmap(24,24)
        if not pixmap.isNull():
            painter=QPainter(pixmap);painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn);painter.fillRect(pixmap.rect(),QColor(color));painter.end()
            self.pin.setIcon(QIcon(pixmap))
    def preset(self,slot,name):
        presets={'OpenAI':('openai','https://api.openai.com/v1','gpt-4o-mini-transcribe' if slot=='transcription' else 'gpt-4.1-mini'),
                 'Groq':('openai','https://api.groq.com/openai/v1','whisper-large-v3-turbo' if slot=='transcription' else ''),
                 'Google Gemini':('gemini','https://generativelanguage.googleapis.com/v1beta',''),
                 'Anthropic':('anthropic','https://api.anthropic.com/v1','')}
        if name not in presets:return
        fmt,url,model=presets[name];f=self.fields[slot]
        f['format'].setCurrentIndex(f['format'].findData(fmt));f['base_url'].setText(url);f['model'].setText(model);f['model'].setPlaceholderText('Model ID from your provider');f['key'].clear();f['forget'].setChecked(False)
    def closeEvent(self,event):
        event.ignore();self.hide();self.controller.schedule_idle()

class Controller(QObject):
    def __init__(self,app):
        super().__init__();self.app=app
        try:self.config=api.load_config()
        except api.UserError:self.config=json.loads(json.dumps(api.DEFAULT))
        self.theme=Theme(self);self.theme.changed.connect(self.style)
        self.window=Window(self);self.events=Events();self.events.finished.connect(self.done)
        self.job=None;self.serial=0;self.cancellation=None;self.messages=[];self.target={};self.recording=None;self.audio=None;self.cancel_record=False;self.record_started=0;self.dictate_to_chat=False
        self.timer=QTimer(self);self.timer.setInterval(1000);self.timer.timeout.connect(self.record_tick)
        self.idle=QTimer(self);self.idle.setSingleShot(True);self.idle.setInterval(30000);self.idle.timeout.connect(self.idle_exit)
        self.server=QLocalServer(self);QLocalServer.removeServer(SOCKET)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not self.server.listen(SOCKET):raise RuntimeError('Cannot open the local control socket')
        self.connections=[];self.server.newConnection.connect(self.accept)
        self.set_state('idle');self.style()
    def style(self):
        colors=self.theme.colors
        bg=colors.get('surface','#151515');surface=colors.get('surface_container','#242424');fg=colors.get('on_surface','#eeeeee');accent=colors.get('primary','#a7c080');muted=colors.get('on_surface_variant','#bbbbbb');border=colors.get('outline_variant','#454545')
        on_accent=colors['on_primary']
        def rgba(value,alpha):
            color=QColor(value);return f'rgba({color.red()},{color.green()},{color.blue()},{alpha})'
        self.window.glass_tint=QColor(accent);self.window.glass_tint.setAlpha(12);self.window.update()
        palette=self.app.palette();palette.setColor(QPalette.ColorRole.PlaceholderText,QColor(muted));self.app.setPalette(palette)
        self.app.setFont(QFont('Google Sans Flex',11))
        self.window.update_pin_icon(on_accent if self.window.pin.isChecked() else fg)
        color=QColor(surface);glass=f'rgba({color.red()},{color.green()},{color.blue()},220)'
        self.app.setStyleSheet(f'''QWidget {{ background:transparent;color:{fg}; }} QWidget#overlay {{ background:transparent; }} QWidget#header,QWidget#panel {{ background:{glass};border-radius:16px; }} QLabel#heading {{ font-size:23px;font-weight:600; }} QLabel#muted,QLabel#hint {{ color:{muted};background:{glass};border-radius:8px;padding:6px; }} QPushButton {{ background:{glass};border:1px solid {border};border-radius:12px;padding:10px 16px; }} QPushButton:hover {{ border-color:{accent}; }} QPushButton:checked {{ background:{accent};color:{on_accent}; }} QPushButton:disabled {{ color:{muted}; }} QLineEdit,QPlainTextEdit,QTextBrowser,QComboBox {{ background:{glass};border:1px solid {border};border-radius:12px;padding:10px;selection-background-color:{accent};selection-color:{on_accent}; }} QComboBox QAbstractItemView {{ background:{surface}; }} QGroupBox {{ border:1px solid {border};border-radius:12px;margin-top:15px;padding:16px 8px 8px; }} QGroupBox::title {{ subcontrol-origin:margin;left:16px; }} QTabWidget::pane {{ border:0; }} QTabBar::tab {{ background:{glass};padding:10px 22px;border-bottom:2px solid transparent; }} QTabBar::tab:selected {{ color:{accent};border-bottom-color:{accent}; }} QScrollArea {{ border:0; }}''')
        if self.window.chat_mode:
            self.app.setStyleSheet(self.app.styleSheet()+f'''QWidget#header,QTextBrowser#conversation,QPlainTextEdit#prompt,QLabel#muted {{ background:transparent;border:0; }} QLabel#heading {{ font-size:18px; }} QPlainTextEdit#prompt {{ padding:6px; }} QWidget#composer {{ background:{rgba(accent,18)};border:1px solid {rgba(accent,70)};border-radius:22px; }} QPushButton {{ background:transparent;border:0;border-radius:19px; }} QPushButton:hover {{ background:{rgba(accent,35)}; }} QPushButton:checked,QPushButton#send:enabled {{ background:{accent};color:{on_accent}; }} QPushButton:disabled {{ color:{rgba(fg,100)}; }}''')
    def set_state(self,state):
        api.write_json(STATUS,{'state':state,'pid':os.getpid(),'updated':int(time.time())})
        self.window.voice_state.setText({'idle':'Ready to listen','recording':'Listening…','transcribing':'Transcribing…','chat':'Waiting for a reply…','preparing':'Preparing…','settings':'Saving settings…'}.get(state,state))
        self.window.record.setText('Stop & transcribe' if state=='recording' else 'Start dictation')
        self.window.send.setEnabled(state=='idle');self.window.save.setEnabled(state=='idle')
        self.window.stop.setEnabled(state=='chat');self.window.clear.setEnabled(state=='idle')
    def accept(self):
        while self.server.hasPendingConnections():
            conn=self.server.nextPendingConnection();self.connections.append(conn)
            conn.readyRead.connect(lambda c=conn:self.read_action(c))
            conn.disconnected.connect(lambda c=conn:self.release(c))
            if conn.bytesAvailable():self.read_action(conn)
    def release(self,conn):
        if conn in self.connections:self.connections.remove(conn)
        conn.deleteLater()
    def read_action(self,conn):
        if conn.bytesAvailable()>128:conn.abort();return
        if not conn.canReadLine():return
        action=bytes(conn.readLine()).decode(errors='ignore').strip();conn.disconnectFromServer()
        if action in ['menu','settings','chat','dictate','cancel','quit']:self.action(action)
    def show(self,index):
        self.idle.stop();self.window.tabs.setCurrentIndex(index);self.window.set_page(index);self.window.show();self.window.raise_();self.window.activateWindow()
        self.window.overlay.shown()
        if index==1:self.window.input.setFocus()
    def action(self,action):
        self.idle.stop()
        if action in ['menu','settings','chat']:
            current=api.active_window()
            if current.get('pid')!=os.getpid():self.target=current
            self.show(1 if action=='chat' else 2 if action=='settings' or not api.CONFIG.exists() else 0)
        elif action=='dictate':self.toggle_dictation()
        elif action=='cancel':self.cancel()
        elif action=='quit':self.shutdown();self.app.quit()
    def notify(self,message):
        self.window.message.setText(message)
        self.window.message.setVisible(bool(message))
        if not self.window.isVisible():
            subprocess=__import__('subprocess')
            try:subprocess.Popen(['notify-send','-a','Voice & Chat','-t','3500','Voice & Chat',message],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            except OSError:pass
    def run_job(self,kind,work,callback):
        if self.job:return
        self.idle.stop();self.serial+=1;number=self.serial;self.cancellation=threading.Event();cancel=self.cancellation
        self.job=(number,kind,callback);self.set_state(kind)
        self.window.message.setText({'chat':'Waiting for a reply…','settings':'Saving to your desktop keyring…','preparing':'Checking transcription settings…','transcribing':'Transcribing…'}.get(kind,''))
        self.window.message.setVisible(bool(self.window.message.text()))
        def run():
            try:result=work(cancel);error=''
            except api.UserError as e:result=None;error=str(e)
            except Exception:result=None;error='The operation failed. Check your settings and try again.'
            self.events.finished.emit(number,result,error)
        threading.Thread(target=run,daemon=True).start()
    def done(self,number,result,error):
        if not self.job or self.job[0]!=number:return
        _,kind,callback=self.job;cancelled=self.cancellation.is_set();self.job=None;self.set_state('idle')
        if cancelled:self.notify('Cancelled.')
        elif error:
            self.notify(error)
            if 'API key' in error and kind!='chat':self.show(2)
        else:callback(result)
        self.schedule_idle()
    def toggle_dictation(self):
        if self.recording:
            self.stop_recording();return
        if self.job:self.notify('Finish or cancel the current operation first.');return
        current=api.active_window()
        self.dictate_to_chat=current.get('pid')==os.getpid() and self.window.tabs.currentIndex()==1
        if current.get('pid')!=os.getpid():self.target=current
        def prepare(cancel):
            p=api.validate_profile(self.config['transcription'],'transcription');api.credential('transcription',p)
        self.run_job('preparing',prepare,lambda _:self.start_recording())
    def start_recording(self):
        self.window.hide();self.idle.stop();self.cancel_record=False
        fd,name=tempfile.mkstemp(dir=RUNTIME,prefix='recording-',suffix='.wav');os.close(fd);self.audio=Path(name)
        proc=QProcess(self);self.recording=proc
        proc.setProgram('/usr/bin/python3');proc.setArguments([str(Path(__file__).with_name('recorder.py')),'--rate','16000','--channels','1','--format','s16','--sample-count','1920000',str(self.audio)])
        proc.setStandardErrorFile(QProcess.nullDevice());proc.setStandardOutputFile(QProcess.nullDevice())
        proc.finished.connect(lambda code,status,p=proc:self.record_finished(p,code))
        proc.errorOccurred.connect(lambda error,p=proc:self.record_error(p,error))
        proc.start();self.record_started=time.monotonic();self.set_state('recording');self.timer.start()
        self.notify('Listening. Press Ctrl + Super + D again to transcribe.')
    def record_error(self,proc,error):
        if error==QProcess.ProcessError.FailedToStart and self.recording==proc:
            self.recording=None;self.timer.stop();self.delete_audio();self.set_state('idle');self.notify('The microphone recorder could not start.');self.schedule_idle();proc.deleteLater()
    def record_tick(self):
        elapsed=int(time.monotonic()-self.record_started)
        self.window.voice_state.setText(f'Listening · {elapsed//60}:{elapsed%60:02}')
        if elapsed>=120:self.stop_recording()
    def stop_recording(self):
        proc=self.recording
        if proc and proc.state()!=QProcess.ProcessState.NotRunning:
            try:os.kill(proc.processId(),signal.SIGINT)
            except ProcessLookupError:pass
            QTimer.singleShot(2000,lambda p=proc:self.kill_stuck_recorder(p))
    def kill_stuck_recorder(self,proc):
        if self.recording is proc and proc.state()!=QProcess.ProcessState.NotRunning:proc.kill()
    def record_finished(self,proc,code):
        if self.recording is not proc:return
        self.timer.stop();self.recording=None;proc.deleteLater();path=self.audio;self.audio=None
        if self.cancel_record or (code not in [0,1,130] and time.monotonic()-self.record_started < 119):
            if path:path.unlink(missing_ok=True)
            self.set_state('idle');self.notify('Recording cancelled.' if self.cancel_record else 'Microphone recording failed. Check the input device.');self.schedule_idle();return
        config=json.loads(json.dumps(self.config));target=dict(self.target);to_chat=self.dictate_to_chat
        def work(cancel):
            try:return api.transcribe(config,path,cancel)
            finally:path.unlink(missing_ok=True)
        def completed(text):
            self.window.transcript.setPlainText(text)
            if to_chat:
                self.window.input.insertPlainText(text);self.show(1);self.notify('Transcript added to your draft. Press Send when ready.');return
            try:self.notify(api.paste_transcript(text,target,config.get('auto_paste',True)))
            except api.UserError as e:self.notify(str(e));self.show(0)
        self.run_job('transcribing',work,completed)
    def delete_audio(self):
        if self.audio:self.audio.unlink(missing_ok=True);self.audio=None
    def cancel(self):
        if self.job and self.job[1]=='settings':
            self.notify('Please let settings finish saving.');return
        if self.recording:self.cancel_record=True;self.stop_recording()
        elif self.job:self.cancellation.set();self.notify('Cancelling…')
        else:self.notify('Nothing is recording or waiting for a reply.')
    def send_chat(self):
        if self.job or self.recording:self.notify('Finish or cancel the current operation first.');return
        text=self.window.input.toPlainText().strip()
        if not text:return
        if len(text)>12000:self.notify('Please keep each message under 12,000 characters.');return
        pending=self.messages+[{'role':'user','content':text}];config=json.loads(json.dumps(self.config))
        self.window.show_conversation()
        self.render_messages(pending)
        def completed(answer):
            self.messages=(pending+[{'role':'assistant','content':answer}])[-20:]
            self.render_messages(self.messages)
            if self.window.input.toPlainText().strip()==text:self.window.input.clear()
            self.notify('Reply ready.')
        self.run_job('chat',lambda cancel:api.chat(config,pending,cancel),completed)
    def render_messages(self,messages):
        paragraphs=[]
        for message in messages:
            alignment='right' if message['role']=='user' else 'left'
            paragraphs.append('<p align="'+alignment+'" style="margin-top:12px;margin-bottom:18px;">'+html.escape(message['content']).replace('\n','<br>')+'</p>')
        self.window.history.setHtml(''.join(paragraphs))
        self.window.history.moveCursor(QTextCursor.MoveOperation.End)
    def new_chat(self):
        if self.job:self.notify('Stop the current reply before starting a new chat.');return
        self.messages=[];self.window.history.clear();self.window.input.clear();self.window.message.clear()
        self.window.message.hide()
        self.window.history.hide()
        if self.window.chat_mode:self.window.resize_overlay(680,180)
    def save_settings(self):
        if self.job or self.recording:return
        try:
            config={};keys={};forget={}
            for slot,f in self.window.fields.items():
                config[slot]=api.validate_profile({'format':f['format'].currentData(),'base_url':f['base_url'].text(),'model':f['model'].text()},slot)
                keys[slot]=f['key'].text().strip();forget[slot]=f['forget'].isChecked()
                if keys[slot] and forget[slot]:raise api.UserError('Choose either a new key or Remove saved key, not both.')
            language=self.window.language.text().strip()
            if language and not __import__('re').fullmatch('[a-zA-Z-]{2,12}',language):raise api.UserError('Use a language code such as en, ml, or hi, or leave it blank.')
            config['language']=language;config['auto_paste']=self.window.auto_paste.isChecked()
        except api.UserError as e:self.notify(str(e));return
        def work(cancel):
            for slot,p in ((s,config[s]) for s in ['transcription','chat']):
                if keys[slot]:api.secret(slot,p,'store',keys[slot])
                elif forget[slot]:api.secret(slot,p,'clear')
            api.write_json(api.CONFIG,config)
        def completed(_):
            self.config=config
            for f in self.window.fields.values():f['key'].clear();f['forget'].setChecked(False)
            self.notify('Settings saved. Use Ctrl + Super + D for dictation or Ctrl + Super + A for chat.')
        self.run_job('settings',work,completed)
    def schedule_idle(self):
        if not self.window.isVisible() and not self.job and not self.recording:self.idle.start()
    def idle_exit(self):
        if not self.window.isVisible() and not self.job and not self.recording:self.app.quit()
    def shutdown(self):
        self.theme.stop()
        self.window.overlay.stop()
        if self.cancellation:self.cancellation.set()
        if self.recording:
            self.recording.blockSignals(True);self.recording.kill();self.recording.waitForFinished(1000)
        self.delete_audio()
        for audio in RUNTIME.glob('recording-*.wav'):audio.unlink(missing_ok=True)
        api.write_json(STATUS,{'state':'idle'});self.server.close()

app=QApplication(sys.argv[:1]);app.setApplicationName('ii-voice-ai');app.setDesktopFileName('ii-voice-ai');app.setQuitOnLastWindowClosed(False)
controller=Controller(app);app.aboutToQuit.connect(controller.shutdown)
# Recover only stale recordings belonging to this dedicated runtime directory.
for stale in RUNTIME.glob('recording-*.wav'):stale.unlink(missing_ok=True)
signal.signal(signal.SIGTERM,lambda *_:app.quit())
signal.signal(signal.SIGINT,lambda *_:app.quit())
QTimer.singleShot(0,lambda:controller.action(ACTION))
sys.exit(app.exec())
