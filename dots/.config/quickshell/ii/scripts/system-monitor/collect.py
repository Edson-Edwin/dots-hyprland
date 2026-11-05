#!/usr/bin/env python3
"""Read-only local metrics. One bounded JSON record every two seconds while open."""
import json,os,re,select,signal,subprocess,sys,time
from pathlib import Path
import psutil

INTERVAL=2
DETAIL_INTERVAL=6
PAGES=('overview','processes','ports')
SCANNER=Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'illogical-impulse/system-monitor/process-scan'
STATES={'R':'running','S':'sleeping','D':'disk-sleep','T':'stopped','t':'tracing-stop',
        'Z':'zombie','X':'dead','I':'idle','W':'waking','P':'parked'}
TICKS=os.sysconf('SC_CLK_TCK')
PAGE_SIZE=os.sysconf('SC_PAGE_SIZE')

def process_snapshot():
    if SCANNER.is_file():
        result=subprocess.run([SCANNER],capture_output=True,check=True,timeout=3)
        for pid,start,ticks,pages,state,name in json.loads(result.stdout):
            yield pid,start,ticks/TICKS,pages*PAGE_SIZE,STATES.get(state,'unknown'),name
    else:
        # Portable fallback for installations without the optional native helper.
        for proc in psutil.process_iter(['pid','name','memory_info','cpu_times','create_time','status'],ad_value=None):
            p=proc.info
            if p['cpu_times'] and p['memory_info']:
                yield (p['pid'],p['create_time'],p['cpu_times'].user+p['cpu_times'].system,
                       p['memory_info'].rss,p['status'],p['name'])


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
        for pid,start,cpu,rss,state,name in process_snapshot():
            key=(pid,start);current[key]=cpu
            usage=100*rate(cpu,self.previous.get(key,cpu),elapsed)
            rows.append({'pid':pid,'name':(name or 'Unknown')[:80],'rss':rss,
                         'cpu':round(usage,1),'state':state or 'unknown'})
        self.previous=current;self.process_time=now
        count=len(rows)
        # Bounded payload, retaining the heaviest processes by both CPU and RAM.
        selected={p['pid']:p for p in sorted(rows,key=lambda p:p['rss'],reverse=True)[:100]}
        selected.update({p['pid']:p for p in sorted(rows,key=lambda p:p['cpu'],reverse=True)[:100]})
        return list(selected.values()),count
    def ports(self):
        try:
            result=subprocess.run(['ss','-H','-lntup'],capture_output=True,text=True,timeout=2,env={**os.environ,'LC_ALL':'C'})
            ports=parse_ports(result.stdout);port_error='' if result.returncode==0 else 'Socket list unavailable'
        except (OSError,subprocess.TimeoutExpired):ports=[];port_error='Socket list unavailable'
        return {'ports':ports,'port_error':port_error}

    def detail(self,now):
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
        self.details={'process_count':len(psutil.pids()),
                      'temperatures':temperatures[:12],'disks':disks,'zram':zram}
        self.detail_time=now
    def sample(self):
        now=time.monotonic();elapsed=now-self.last_time if self.last_time is not None else 0
        vm=psutil.virtual_memory();swap=psutil.swap_memory();cores=psutil.cpu_percent(percpu=True)
        cpu=sum(cores)/len(cores) if cores else 0
        counters=psutil.net_io_counters(pernic=True)
        try:stats=psutil.net_if_stats()
        except OSError:stats={}
        rx=tx=0;interfaces=[]
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
    # The shell starts in overview and sends page changes over this single pipe.
    args=sys.argv[1:]
    page=args[args.index('--page')+1] if '--page' in args else 'overview'
    if page not in PAGES:raise SystemExit('unknown system monitor page')
    interactive='--interactive' in args
    sampler=Sampler()
    generation=0;next_sample=next_detail=0;pending=b''
    def emit(data):
        print(json.dumps(data,separators=(',',':'),allow_nan=False),flush=True)
    while True:
        now=time.monotonic()
        if now>=next_sample:
            next_sample=now+INTERVAL
            try:emit(sampler.sample())
            except (OSError,ValueError,psutil.Error):emit({'error':'Metrics temporarily unavailable'})
        if page!='overview' and now>=next_detail:
            next_detail=now+DETAIL_INTERVAL
            try:
                detail={'processes':sampler.processes(now)[0]} if page=='processes' else sampler.ports()
            except (OSError,ValueError,subprocess.SubprocessError,psutil.Error):
                detail={'detail_error':'Process list unavailable' if page=='processes' else 'Socket list unavailable'}
            emit({'page':page,'generation':generation,**detail})
        if '--once' in args:return
        deadline=min(next_sample,next_detail) if page!='overview' else next_sample
        delay=max(0,deadline-time.monotonic())
        if not interactive:
            time.sleep(delay)
        elif select.select([sys.stdin],[],[],delay)[0]:
            chunk=os.read(sys.stdin.fileno(),4096)
            if not chunk:return
            pending+=chunk
            lines=pending.split(b'\n');pending=lines.pop()
            for line in lines:
                fields=line.decode('ascii','ignore').split()
                if len(fields)!=2 or fields[0] not in PAGES or not fields[1].isdigit():continue
                page,generation=fields[0],int(fields[1])
                sampler.previous.clear();sampler.process_time=None;next_detail=0
if __name__=='__main__':
    try:main()
    except BrokenPipeError:pass
