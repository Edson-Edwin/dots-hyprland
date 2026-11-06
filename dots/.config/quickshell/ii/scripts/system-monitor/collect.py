#!/usr/bin/env python3
"""Read-only local metrics. One bounded JSON record every two seconds while open."""
import json,os,re,signal,subprocess,sys,time
from pathlib import Path
import psutil

INTERVAL=2

def rate(now,before,elapsed):
    return max(0,now-before)/elapsed if elapsed>0 else 0

def parse_ports(text):
    rows=[]
    for line in text.splitlines():
        fields=line.split(None,6)
        if len(fields)<6:continue
        protocol,state,_,_,address,_=fields[:6]
        if protocol not in ('tcp','udp'):continue
        owner=fields[6] if len(fields)>6 else ''
        names=re.findall(r'\("([^"\n]+)",pid=(\d+)',owner)
        rows.append({'protocol':protocol.upper(),'address':address[:200],
                     'owner':', '.join(f'{name[:50]} · {pid}' for name,pid in names[:3]) or 'Owner unavailable',
                     'state':state})
    return sorted(rows,key=lambda x:(x['protocol'],x['address']))[:256]

class Sampler:
    def __init__(self):
        self.previous={};self.process_time=None;self.last_time=None;self.net={};self.disk=(0,0)
        self.detail_time=0;self.details={};psutil.cpu_percent(percpu=True)
    def processes(self,now):
        rows=[];current={};elapsed=now-self.process_time if self.process_time is not None else 0
        for proc in psutil.process_iter(['pid','name','memory_info','cpu_times','create_time','status'],ad_value=None):
            p=proc.info
            if p['cpu_times'] is None or p['memory_info'] is None:continue
            key=(p['pid'],p['create_time']);cpu=p['cpu_times'].user+p['cpu_times'].system
            usage=100*rate(cpu,self.previous.get(key,cpu),elapsed)
            current[key]=cpu
            rows.append({'pid':p['pid'],'name':(p['name'] or 'Unknown')[:80],
                         'rss':p['memory_info'].rss,'cpu':round(usage,1),'state':p['status'] or 'unknown'})
        self.previous=current;self.process_time=now
        count=len(rows)
        # Bounded payload, retaining the heaviest processes by both CPU and RAM.
        selected={p['pid']:p for p in sorted(rows,key=lambda p:p['rss'],reverse=True)[:100]}
        selected.update({p['pid']:p for p in sorted(rows,key=lambda p:p['cpu'],reverse=True)[:100]})
        return list(selected.values()),count
    def detail(self,now):
        processes,count=self.processes(now)
        try:
            result=subprocess.run(['ss','-H','-lntup'],capture_output=True,text=True,timeout=2,env={**os.environ,'LC_ALL':'C'})
            ports=parse_ports(result.stdout);port_error='' if result.returncode==0 else 'Socket list unavailable'
        except (OSError,subprocess.TimeoutExpired):ports=[];port_error='Socket list unavailable'
        temperatures=[]
        try:
            for device,entries in psutil.sensors_temperatures().items():
                for entry in entries:
                    if entry.current is not None and -20<entry.current<160:
                        temperatures.append({'label':(entry.label or device)[:40],'value':round(entry.current,1)})
        except (OSError,AttributeError):pass
        disks=[]
        for mount in ('/','/home'):
            try:
                d=psutil.disk_usage(mount);disks.append({'mount':mount,'used':d.used,'total':d.total,'percent':d.percent})
            except OSError:pass
        zram=0
        for p in Path('/sys/block').glob('zram*/mm_stat'):
            try:zram+=int(p.read_text().split()[2])
            except (OSError,ValueError,IndexError):pass
        self.details={'processes':processes,'process_count':count,'ports':ports,'port_error':port_error,
                      'temperatures':temperatures[:12],'disks':disks,'zram':zram}
        self.detail_time=now
    def sample(self):
        now=time.monotonic();elapsed=now-self.last_time if self.last_time is not None else 0
        vm=psutil.virtual_memory();swap=psutil.swap_memory();cores=psutil.cpu_percent(percpu=True)
        cpu=sum(cores)/len(cores) if cores else 0
        counters=psutil.net_io_counters(pernic=True);stats=psutil.net_if_stats();rx=tx=0;interfaces=[]
        for name,value in counters.items():
            if name=='lo' or not (Path('/sys/class/net')/name/'device').exists():continue
            if name not in stats or not stats[name].isup:continue
            interfaces.append(name)
            old=self.net.get(name,(value.bytes_recv,value.bytes_sent))
            rx+=rate(value.bytes_recv,old[0],elapsed);tx+=rate(value.bytes_sent,old[1],elapsed)
        self.net={name:(v.bytes_recv,v.bytes_sent) for name,v in counters.items()}
        io=psutil.disk_io_counters();disk=(io.read_bytes,io.write_bytes) if io else (0,0)
        read=rate(disk[0],self.disk[0],elapsed);write=rate(disk[1],self.disk[1],elapsed)
        self.disk=disk;self.last_time=now
        if not self.details or now-self.detail_time>=5.8:self.detail(now)
        return {'cpu':round(cpu,1),'cores':cores,'ram_used':vm.total-vm.available,'ram_total':vm.total,
                'ram_available':vm.available,'ram_cache':getattr(vm,'cached',0),'ram_percent':vm.percent,
                'swap_used':swap.used,'swap_total':swap.total,'swap_percent':swap.percent,
                'rx':rx,'tx':tx,'interfaces':interfaces,'disk_read':read,'disk_write':write,
                'load':list(os.getloadavg()),'uptime':int(time.time()-psutil.boot_time()),**self.details}

def main():
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    # Exit with Quickshell even if it crashes; do not become a background daemon.
    parent=os.getppid()
    try:
        import ctypes
        ctypes.CDLL(None).prctl(1,signal.SIGTERM)
        if os.getppid()!=parent:return
    except (OSError,AttributeError):pass
    sampler=Sampler()
    while True:
        start=time.monotonic()
        try:print(json.dumps(sampler.sample(),separators=(',',':'),allow_nan=False),flush=True)
        except BrokenPipeError:return
        except (OSError,ValueError,psutil.Error):print('{"error":"Metrics temporarily unavailable"}',flush=True)
        if '--once' in sys.argv:return
        time.sleep(max(.1,INTERVAL-(time.monotonic()-start)))
if __name__=='__main__':main()
