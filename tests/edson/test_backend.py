import sys,threading,tempfile,wave,subprocess,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str((Path(__file__).resolve().parents[2] / 'dots/.config/hypr/hyprland/scripts/edson/voice-ai')))
import backend as b
cancel=threading.Event()
with tempfile.TemporaryDirectory() as d:
 audio=Path(d)/'test.wav'
 with wave.open(str(audio),'wb') as w:w.setparams((1,2,16000,0,'NONE',''));w.writeframes(b'\0\0'*3200)
 for kind in ['openai','gemini','anthropic']:
  config=json.loads(json.dumps(b.DEFAULT));config['chat']={'format':kind,'base_url':'https://example.org/v1','model':'test-model'}
  response={'openai':{'choices':[{'message':{'content':'Hello'}}]},'gemini':{'candidates':[{'content':{'parts':[{'text':'Hello'}]}}]},'anthropic':{'content':[{'type':'text','text':'Hello'}]}}[kind]
  with patch.object(b,'credential',return_value='test-key'),patch.object(b,'request_json',return_value=response) as request:
   assert b.chat(config,[{'role':'user','content':'Hello','tools':['bad']},{'role':'tool','content':'bad'}],cancel)=='Hello'
   payload=request.call_args.kwargs['payload'];serialized=json.dumps(payload)
   assert '"tools"' not in serialized and '"role": "tool"' not in serialized and '"function_call"' not in serialized
  if kind!='anthropic':
   config['transcription']=dict(config['chat'])
   response={'text':'spoken words'} if kind=='openai' else {'candidates':[{'content':{'parts':[{'text':'spoken words'}]}}]}
   with patch.object(b,'credential',return_value='test-key'),patch.object(b,'request_json',return_value=response) as request:
    assert b.transcribe(config,audio,cancel)=='spoken words'
    if kind=='openai':assert request.call_args.kwargs['files']['file'][0]=='dictation.wav'
    else:assert 'inline_data' in json.dumps(request.call_args.kwargs['payload'])
 print('PASS: three chat formats, two transcription formats, text-only outbound requests')
 for url in ['http://example.org/v1','https://key@example.org/v1','https://example.org/v1?key=secret']:
  try:b.validate_profile({'format':'openai','base_url':url,'model':'test'},'chat');raise AssertionError(url)
  except b.UserError:pass
 assert b.validate_profile({'format':'openai','base_url':'http://127.0.0.1:9999/v1','model':'test'},'chat')
 a={'format':'openai','base_url':'https://one.test/v1'};c={'format':'openai','base_url':'https://two.test/v1'}
 assert b.secret_id('chat',a)!=b.secret_id('chat',c)
 assert b.secret_id('chat',a)!=b.secret_id('transcription',a)
 try:b.text_result({'choices':[{'message':{'tool_calls':[{'function':{'name':'run_command'}}]}}]},'openai');raise AssertionError()
 except b.UserError:pass
 print('PASS: endpoint validation, provider-scoped credentials, tool-only replies rejected')
 target={'address':'0x123','pid':10,'class':'kitty'}
 with patch.object(b,'active_window',return_value={'address':'0x456','pid':11}),patch.object(b.subprocess,'run') as run,patch.object(b.time,'sleep'):
  assert 'changed' in b.paste_transcript('hello',target,True)
  assert len(run.call_args_list)==1 and run.call_args.args[0][0]=='wl-copy'
 with patch.object(b,'active_window',return_value=target),patch.object(b.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'ok\n')) as run,patch.object(b.time,'sleep'):
  assert 'pasted' in b.paste_transcript('line one\nline two',target,True)
  assert run.call_args_list[0].kwargs['input']==b'line one line two'
  assert run.call_args_list[1].args[0][-1]=='hl.dsp.send_shortcut({mods="CTRL SHIFT",key="V",window="address:0x123"})'
  assert all('Return' not in str(x) for x in run.call_args_list)
 print('PASS: changed-focus guard, terminal paste shortcut, no newline/Enter submission')
 with patch.object(b.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'',b'')) as run:
  b.secret('chat',a,'store','sample-secret')
  assert 'sample-secret' not in str(run.call_args.args)
  assert run.call_args.kwargs['input']==b'sample-secret'
 print('PASS: keys passed over stdin, never process arguments')
class Response:
 status_code=200
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def iter_content(self,n):yield b'{"ok":true}'
with patch.object(b.requests,'post',return_value=Response()) as post:
 assert b.request_json('https://example.test/v1','secret','openai',payload={'test':True})=={'ok':True}
 assert post.call_args.kwargs['allow_redirects'] is False
 assert post.call_args.kwargs['timeout']==(8,90)
class Unauthorized(Response):status_code=401
with patch.object(b.requests,'post',return_value=Unauthorized()):
 try:b.request_json('https://example.test','do-not-leak','openai');raise AssertionError()
 except b.UserError as e:assert 'do-not-leak' not in str(e) and '401' in str(e)
class Oversized(Response):
 def iter_content(self,n):yield b' '*(b.MAX_RESPONSE+1)
with patch.object(b.requests,'post',return_value=Oversized()):
 try:b.request_json('https://example.test','secret','openai');raise AssertionError()
 except b.UserError as e:assert 'limit' in str(e)
print('PASS: no redirects, bounded time/response size, sanitized provider errors')
