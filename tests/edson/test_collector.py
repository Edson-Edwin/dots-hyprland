import sys
from pathlib import Path
sys.path.insert(0,str((Path(__file__).resolve().parents[2] / 'dots/.config/quickshell/ii/scripts/system-monitor')))
from collect import parse_ports,rate
assert rate(120,100,2)==10 and rate(10,100,2)==0 and rate(10,0,0)==0
rows=parse_ports('tcp LISTEN 0 128 127.0.0.1:8080 0.0.0.0:* users:(("demo",pid=12,fd=3))\nudp UNCONN 0 0 [::]:5353 [::]:*\ninvalid\n')
assert len(rows)==2 and rows[0]['owner']=='demo · 12' and rows[1]['address']=='[::]:5353'
assert rows[1]['owner']=='Owner unavailable'
assert len(parse_ports(('tcp LISTEN 0 0 *:80 *:*\n')*300))==256
print('PASS: rate resets/first sample, TCP/UDP/IPv6 parsing, unavailable owners, bounded port list')
