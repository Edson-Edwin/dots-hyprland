"""Exercise the same tab protocol Quickshell uses, without enumerating real sockets."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

collector=Path(__file__).resolve().parents[2]/'dots/.config/quickshell/ii/scripts/system-monitor/collect.py'

def test_switching():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        scanner=root/'illogical-impulse/system-monitor/process-scan'
        scanner.parent.mkdir(parents=True)
        calls=root/'calls'
        for exe,output in [(scanner,'[[42,123,456,789,"S","sample"]]'),
                           (root/'ss','tcp LISTEN 0 10 *:1234 *:*')]:
            exe.write_text(f'#!/bin/sh\necho "{exe.name}" >> "$CALLS"\necho \'{output}\'\n')
            exe.chmod(0o755)
        env={**os.environ,'XDG_DATA_HOME':temp,'PATH':temp+':'+os.environ['PATH'],'CALLS':str(calls)}
        p=subprocess.Popen([sys.executable,'-u',collector,'--interactive'],stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,text=True,env=env)
        def send(page,generation):
            p.stdin.write(f'{page} {generation}\n');p.stdin.flush()
        def frame(page=None):
            while True:
                line=p.stdout.readline()
                assert line,'collector exited early'
                record=json.loads(line)
                if record.get('page')==page:return record
        try:
            assert 'cpu' in frame() and not calls.exists()
            send('processes',1)
            proc=frame('processes')
            assert proc['generation']==1 and proc['processes'][0]['pid']==42 and 'ports' not in proc
            send('ports',2)
            port=frame('ports')
            assert port['generation']==2 and port['ports'][0]['address']=='*:1234' and 'processes' not in port
            send('overview',3)
            # Stay on Overview longer than a complete detail interval.
            for _ in range(4):
                record=frame()
                assert 'cpu' in record and 'ports' not in record and 'processes' not in record
            assert calls.read_text().splitlines()==['process-scan','ss']
            p.stdin.close()
            assert p.wait(timeout=3)==0
        finally:
            if p.poll() is None:p.kill();p.wait()

if __name__=='__main__':
    test_switching()
    print('PASS: tab-specific scans, immediate switching, uninterrupted graphs, collector shutdown')
