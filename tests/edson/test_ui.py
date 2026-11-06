import os,tempfile,sys,runpy,time,inspect,threading
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QInputMethodEvent,QKeyEvent
from PySide6.QtTest import QTest
ROOT=(Path(__file__).resolve().parents[2] / 'dots/.config/hypr/hyprland/scripts/edson/voice-ai')
sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='voice-ui-test-') as temp:
 os.environ['XDG_RUNTIME_DIR']=temp
 os.environ['XDG_CONFIG_HOME']=temp+'/config'
 os.environ['QT_QPA_PLATFORM']='offscreen'
 os.environ.pop('WAYLAND_DISPLAY',None)
 import backend as api
 def test_exec(app):
  g=inspect.currentframe().f_back.f_globals;c=g['controller'];w=c.window
  def wait():
   end=time.monotonic()+4
   while c.job and time.monotonic()<end:app.processEvents();time.sleep(.01)
   app.processEvents();assert not c.job,'Worker did not finish'
  app.processEvents()
  assert w.tabs.currentIndex()==2
  w.fields['transcription']['key'].setText('test-secret')
  w.fields['chat']['key'].setText('test-secret')
  with patch.object(api,'secret',return_value='') as keyring:
   c.save_settings();wait();assert keyring.call_count==2
  saved=api.CONFIG.read_text();assert 'test-secret' not in saved
  assert all(not f['key'].text() for f in w.fields.values())
  c.show(1);w.input.setPlainText('Hello')
  assert w.tabs.tabBar().isHidden() and w.input.height()==46
  with patch.object(api,'chat',return_value='<b>Plain answer</b>'):
   c.send_chat();wait()
  assert '<b>Plain answer</b>' in w.history.toPlainText()
  first=w.history.document().begin()
  assert first.blockFormat().alignment() & Qt.AlignmentFlag.AlignRight
  assert first.next().blockFormat().alignment() & Qt.AlignmentFlag.AlignLeft
  assert w.history.toPlainText()=='Hello\n<b>Plain answer</b>'
  assert not w.input.toPlainText()
  assert w.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
  assert w.windowFlags() & Qt.WindowType.FramelessWindowHint
  w.input.setPlainText('Line one');w.input.moveCursor(w.input.textCursor().MoveOperation.End)
  with patch.object(api,'chat',return_value='Second answer') as chat:
   QTest.keyClick(w.input,Qt.Key.Key_Return,Qt.KeyboardModifier.ShiftModifier)
   w.input.insertPlainText('Line two')
   assert w.input.toPlainText()=='Line one\nLine two';chat.assert_not_called()
   app.processEvents();assert w.input.height()>46,(w.input.height(),w.input.minimumHeight(),w.input.document().blockCount())
   QTest.keyClick(w.input,Qt.Key.Key_Return);wait()
   chat.assert_called_once();assert chat.call_args.args[1][-1]['content']=='Line one\nLine two'
  assert not w.input.toPlainText()
  with patch.object(api,'chat',return_value='Keypad answer') as chat:
   w.input.setPlainText('Keypad');QTest.keyClick(w.input,Qt.Key.Key_Enter);wait();chat.assert_called_once()
  with patch.object(api,'chat') as chat:
   QTest.keyClick(w.input,Qt.Key.Key_Return);chat.assert_not_called()
   w.input.setPlainText('Draft');w.input.inputMethodEvent(QInputMethodEvent('composition',[]))
   QTest.keyClick(w.input,Qt.Key.Key_Return);chat.assert_not_called()
   w.input.inputMethodEvent(QInputMethodEvent('',[]))
   event=QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,'',True)
   w.input.keyPressEvent(event);chat.assert_not_called()
  w.pin.click();assert w.overlay.follow_workspaces and not w.pin.text() and not w.pin.icon().isNull()
  w.pin.click();assert not w.overlay.follow_workspaces
  class Events:
   def __init__(self):self.lines=[b'workspacev2>>2,2\n']
   def bytesAvailable(self):return 20
   def canReadLine(self):return bool(self.lines)
   def readLine(self):return self.lines.pop(0)
  with patch.object(w.overlay,'events',Events()):
   w.pin.setChecked(True);w.overlay.read_events();assert w.isVisible()
  with patch.object(w.overlay,'events',Events()):
   w.pin.setChecked(False);w.overlay.read_events();assert not w.isVisible()
  c.action('chat');assert w.isVisible() and w.tabs.currentIndex()==1
  # A real file event must restyle the existing UI without losing its draft.
  import json
  c.theme.stop();c.theme.path=Path(temp)/'colors.json'
  palette=dict(c.theme.colors,primary='#123456',on_primary='#ffffff')
  c.theme.path.write_text(json.dumps(palette));c.theme.reload()
  w.input.setPlainText('Keep this draft');before=list(c.messages)
  palette['primary']='#abcdef'
  replacement=Path(temp)/'replacement.json';replacement.write_text(json.dumps(palette));os.replace(replacement,c.theme.path)
  end=time.monotonic()+2
  while c.theme.colors['primary']!='#abcdef' and time.monotonic()<end:app.processEvents();time.sleep(.01)
  assert '#abcdef' in app.styleSheet() and 'rgba(171,205,239,18)' in app.styleSheet()
  assert w.input.toPlainText()=='Keep this draft' and c.messages==before
  with patch.object(api,'credential',side_effect=api.UserError('Add an API key for transcription in Settings first.')),patch.object(api,'active_window',return_value={}):
   c.toggle_dictation();wait()
  assert c.recording is None and w.tabs.currentIndex()==2
  assert not w.tabs.tabBar().isHidden()
  c.new_chat();assert not c.messages and not w.history.toPlainText()
  w.close();assert not w.isVisible();assert c.idle.isActive()
  with patch.object(app,'quit') as quit:
   c.idle.setInterval(20)
   end=time.monotonic()+.1
   while time.monotonic()<end:app.processEvents();time.sleep(.005)
   quit.assert_called_once()
  c.shutdown()
  print('PASS: transparent frame, Enter/keypad send, Shift+Enter multiline, IME/repeat guard, pin/workspace behavior, settings/key handling, chat, idle shutdown')
  return 0
 sys.argv=[str(ROOT/'app.py'),'settings']
 with patch.object(QApplication,'exec',test_exec):
  try:runpy.run_path(str(ROOT/'app.py'),run_name='__main__')
  except SystemExit as e:assert e.code==0
