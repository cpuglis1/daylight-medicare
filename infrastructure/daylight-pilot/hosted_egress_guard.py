#!/usr/bin/env python3
"""D191/D194 one-time host egress allowance. No automatic replenishment.

Charge the whole allowance durably BEFORE granting it to nftables. A normal
service restart reuses kernel counters. If the kernel table disappears (including
host reboot), install a closed table. This deliberately trades availability for
crash-safe accounting; an owner must review any subsequent allowance.

This is not an AWS invoice cap. Root/admin traffic and privileged compromise are
outside this guard. The app's provider router still enforces exact destinations.
"""
import argparse
import errno
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess

ROOT=Path('/var/lib/daylight-state/egress')
STATE=ROOT/'allowance.json'
TABLE='daylight_egress'
ORIGIN_BYTES=3*1024**3
APP_BYTES=100*1024**2
SERVICES=('nginx.service','daylight-pilot.service','daylight-test.service')
NFT='/usr/sbin/nft'


def command(args, *, data=None, check=True):
    result=subprocess.run(args,input=data,text=True,capture_output=True,timeout=20)
    if check and result.returncode:
        raise RuntimeError('Egress operation failed: '+Path(args[0]).name)
    return result


def dns_servers(path=Path('/etc/resolv.conf')):
    result=[]
    for line in path.read_text().splitlines():
        fields=line.split()
        if len(fields)>=2 and fields[0]=='nameserver':
            address=ipaddress.ip_address(fields[1])
            if not address.is_loopback and address.compressed not in result:
                result.append(address.compressed)
    if len(result)>4:raise ValueError('Unexpected resolver configuration')
    return result


def rules(uid,resolvers,*,closed=False):
    if type(uid) is not int or uid<=0:raise ValueError('A non-root application UID is required')
    checked=[ipaddress.ip_address(x) for x in resolvers]
    if len(checked)>4:raise ValueError('Too many resolvers')
    # inet applies equally to IPv4 and IPv6. Kernel-originated ACK/RST packets
    # from port 443 are included, not merely nginx application payload.
    rows=[f'table inet {TABLE} {{',
          f' quota origin {{ over {ORIGIN_BYTES} bytes; }}',
          f' quota provider {{ over {APP_BYTES} bytes; }}',
          ' chain output { type filter hook output priority -5; policy accept;',
          f'  meta skuid {uid} ip daddr 169.254.169.254 drop',
          f'  meta skuid {uid} ip6 daddr fd00:ec2::254 drop',
          '  oifname "lo" return']
    if closed:
        rows += ['  tcp sport 443 drop','  udp sport 443 drop',f'  meta skuid {uid} drop']
    else:
        rows += ['  tcp sport 443 quota name "origin" drop',
                 '  udp sport 443 quota name "origin" drop',
                 f'  meta skuid {uid} quota name "provider" drop']
        for address in checked:
            family='ip' if address.version==4 else 'ip6'
            rows += [f'  meta skuid {uid} {family} daddr {address.compressed} udp dport 53 return',
                     f'  meta skuid {uid} {family} daddr {address.compressed} tcp dport 53 return']
        rows += [f'  meta skuid {uid} tcp dport 443 return',f'  meta skuid {uid} drop']
    return '\n'.join(rows+[' }','}',''])


def fingerprint(value):
    """Ignore changing quota usage/handles, retain limits and every actual rule."""
    def clean(item):
        if isinstance(item,dict):return {k:clean(v) for k,v in item.items() if k not in {'handle','used'}}
        if isinstance(item,list):return [clean(v) for v in item if not isinstance(v,dict) or 'metainfo' not in v]
        return item
    return hashlib.sha256(json.dumps(clean(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def live_table():
    # First distinguish a missing table from a failing nft binary/capability.
    listing=json.loads(command([NFT,'-j','list','tables']).stdout)
    exists=any(row.get('table',{}).get('family')=='inet' and row.get('table',{}).get('name')==TABLE
               for row in listing.get('nftables',[]))
    return json.loads(command([NFT,'-j','list','table','inet',TABLE]).stdout) if exists else None


def durable_write(path,value):
    temporary=path.with_suffix('.pending')
    with temporary.open('w') as stream:
        os.chmod(temporary,0o600)
        json.dump(value,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def initialize(uid,resolvers):
    if STATE.exists() or live_table() is not None:
        raise ValueError('An allowance already exists; never silently reset it')
    for service in SERVICES:
        if command(['systemctl','is-active',service],check=False).returncode==0:
            raise ValueError('Initialize only before application/public proxy startup')
    source=rules(uid,resolvers)
    command([NFT,'--check','--file','-'],data=source)
    state={'schema':1,'uid':uid,'resolvers':resolvers,'origin_bytes':ORIGIN_BYTES,
           'app_bytes':APP_BYTES,'phase':'fully_debited'}
    durable_write(STATE,state)  # Crash after this point can only close traffic.
    command([NFT,'--file','-'],data=source)
    state.update(phase='active',fingerprint=fingerprint(live_table()))
    durable_write(STATE,state)
    return {'active':True,'origin_bytes':ORIGIN_BYTES,'app_bytes':APP_BYTES,'automatic_reset':False}


def enforce():
    if not STATE.is_file() or STATE.is_symlink() or STATE.stat().st_mode&0o077:
        raise ValueError('Private durable allowance is required')
    state=json.loads(STATE.read_text())
    if state.get('schema')!=1 or state.get('origin_bytes')!=ORIGIN_BYTES or state.get('app_bytes')!=APP_BYTES:
        raise ValueError('Unexpected allowance state')
    table=live_table()
    if table is not None:
        if state.get('phase') not in {'active','closed'} or state.get('fingerprint')!=fingerprint(table):
            raise ValueError('Existing egress rules need owner review')
        return {'active':state['phase']=='active','reused_counters':True}
    source=rules(state['uid'],state['resolvers'],closed=True)
    command([NFT,'--check','--file','-'],data=source)
    command([NFT,'--file','-'],data=source)
    state.update(phase='closed',fingerprint=fingerprint(live_table()))
    durable_write(STATE,state)
    return {'active':False,'reboot_or_missing_table':True,'owner_review_required':True}


def install_units(script):
    if not script.is_absolute() or not script.is_file() or re.search(r'[^A-Za-z0-9_./-]',str(script)):
        raise ValueError('Use a fixed root-owned installed script path')
    unit=f'''[Unit]
Description=Daylight persistent egress allowance
After=local-fs.target
Before=nginx.service daylight-pilot.service daylight-test.service
RequiresMountsFor=/var/lib/daylight-state
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {script} enforce
RemainAfterExit=yes
UMask=0077
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths={ROOT}
CapabilityBoundingSet=CAP_NET_ADMIN
[Install]
WantedBy=multi-user.target
'''
    Path('/etc/systemd/system/daylight-egress.service').write_text(unit)
    for service in SERVICES:
        directory=Path('/etc/systemd/system')/(service+'.d')
        directory.mkdir(mode=0o755,exist_ok=True)
        path=directory/'10-daylight-egress.conf'
        value='[Unit]\nRequires=daylight-egress.service\nAfter=daylight-egress.service\n'
        if path.exists() and path.read_text()!=value:raise ValueError('Existing dependency differs')
        path.write_text(value)
    command(['systemctl','daemon-reload'])
    command(['systemctl','enable','--now','daylight-egress.service'])


def kernel_self_test():
    """Run ONLY in `unshare --net`; dummy traffic cannot leave this namespace."""
    if os.stat('/proc/self/ns/net').st_ino==os.stat('/proc/1/ns/net').st_ino:
        raise ValueError('Kernel verification requires a separate network namespace')
    if live_table() is not None:raise ValueError('Use an empty test namespace')
    command(['ip','link','set','lo','up'])
    command(['ip','link','add','egresscheck','type','dummy'])
    command(['ip','addr','add','198.18.0.1/24','dev','egresscheck'])
    command(['ip','link','set','egresscheck','up'])
    source=rules(65534,['198.18.0.2']).replace(f'over {ORIGIN_BYTES} bytes','over 512 bytes')
    source=source.replace(f'over {APP_BYTES} bytes','over 128 bytes')
    source=source.replace('  meta skuid 65534 quota name "provider" drop',
        '  udp sport 443 counter comment "accepted_origin"\n'
        '  meta skuid 65534 quota name "provider" drop\n'
        '  meta skuid 65534 counter comment "accepted_provider"')
    command([NFT,'--check','--file','-'],data=source)
    command([NFT,'--file','-'],data=source)
    def emit(sender,payload,address):
        try:sender.sendto(payload,address)
        except OSError as error:
            # OUTPUT drops can report EPERM/EACCES to the sending socket. The
            # nft counter checks below, rather than sendto success, prove that
            # exactly one packet passed each deliberately tiny allowance.
            if error.errno not in {errno.EPERM,errno.EACCES}:raise
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
        sender.bind(('0.0.0.0',443))
        for _ in range(4):emit(sender,b'x'*256,('198.18.0.2',8443))
    child=os.fork()
    if child==0:
        try:
            os.setgid(65534);os.setuid(65534)
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
                for _ in range(4):emit(sender,b'x'*64,('198.18.0.2',53))
            os._exit(0)
        except Exception:os._exit(1)
    _,status=os.waitpid(child,0)
    if status:raise RuntimeError('Fictional provider packet generation failed')
    table=live_table()
    def packets(comment):
        rules=[x['rule'] for x in table['nftables'] if x.get('rule',{}).get('comment')==comment]
        return next(x['counter']['packets'] for x in rules[0]['expr'] if 'counter' in x)
    if packets('accepted_origin')!=1 or packets('accepted_provider')!=1:
        raise RuntimeError('Kernel quota did not stop packets at its byte boundary')
    before=fingerprint(table)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
        sender.bind(('127.0.0.1',443));sender.sendto(b'x'*256,('127.0.0.1',54321))
    after=live_table()
    if fingerprint(after)!=before:raise RuntimeError('Loopback unexpectedly changed quota rules/counters')
    command([NFT,'delete','table','inet',TABLE])
    command([NFT,'--file','-'],data=rules(65534,[],closed=True))
    return {'kernel_quota_exhaustion':True,'loopback_exemption':True,
            'closed_table_compiles':True,'network_namespace_only':True,'provider_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('render','initialize','enforce','install-unit','status','kernel-self-test'))
    parser.add_argument('--uid',type=int)
    args=parser.parse_args()
    if args.command=='render':
        print(rules(args.uid,dns_servers()));return
    if os.geteuid()!=0:raise ValueError('Root-only egress administration')
    if args.command=='kernel-self-test':
        print(json.dumps(kernel_self_test()));return
    os.umask(0o077)
    ROOT.mkdir(mode=0o700,exist_ok=True)
    if args.command=='install-unit':
        install_units(Path(__file__).resolve());return
    with (ROOT/'operation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if args.command=='initialize':print(json.dumps(initialize(pwd.getpwnam('daylight-app').pw_uid,dns_servers())))
        elif args.command=='enforce':print(json.dumps(enforce()))
        else:print(json.dumps({'state':json.loads(STATE.read_text()),'kernel':live_table()}))


if __name__=='__main__':main()
