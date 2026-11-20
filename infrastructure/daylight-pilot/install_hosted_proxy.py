#!/usr/bin/env python3
"""D185-D187/D194: install the private origin proxy; never alter AWS or DNS.

Requires the existing origin token and TLS files. `prepare` writes a root-only
candidate and runs nginx -t without starting a listener. `activate` requires
the exact tested candidate digest and an explicit runtime-access flag.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import socket
import ssl
import subprocess

ROOT=Path('/etc/daylight-pilot')
DIRECTORY=ROOT/'proxy'
CANDIDATE=DIRECTORY/'nginx.conf'
TOKEN=ROOT/'origin-token'
TLS=ROOT/'tls'
NGINX='/usr/sbin/nginx'
OVERRIDE=Path('/etc/systemd/system/nginx.service.d/daylight.conf')


def private_file(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o077:
        raise ValueError('A root-only regular credential/configuration file is required')
    return path.read_bytes()


def render(token):
    # Tokens can be URL-safe random text or hex, never nginx syntax. The exact
    # value is never returned to the terminal, logs, environment or command line.
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}',token):
        raise ValueError('Invalid origin token format')
    return '''user nginx;
worker_processes 2;
pid /run/nginx.pid;
error_log /dev/null crit;
events {
    worker_connections 128;
}
http {
    map_hash_bucket_size 256;
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log off;
    server_tokens off;
    sendfile on;
    keepalive_timeout 15;
    keepalive_requests 100;
    reset_timedout_connection on;
    client_header_timeout 10s;
    client_body_timeout 15s;
    send_timeout 30s;
    client_max_body_size 80000;
    client_body_buffer_size 80000;
    large_client_header_buffers 2 8k;
    client_body_temp_path /run/daylight-nginx/body;
    proxy_temp_path /run/daylight-nginx/proxy;

    # Global bounds work without trusting a caller-supplied forwarding header.
    # Participant-specific pacing and CSRF remain enforced by the application.
    limit_req_zone $server_name zone=daylight_requests:1m rate=30r/s;
    limit_conn_zone $server_name zone=daylight_connections:1m;

    map $host $daylight_backend {
        default "";
        daylightmedicare.com http://127.0.0.1:19093;
        test.daylightmedicare.com http://127.0.0.1:19094;
    }
    map $http_x_daylight_origin_token $daylight_origin_ok {
        default 0;
        "'''+token+'''" 1;
    }

    server {
        listen 443 ssl default_server;
        server_name daylightmedicare.com test.daylightmedicare.com;
        ssl_certificate /etc/daylight-pilot/tls/fullchain.pem;
        ssl_certificate_key /etc/daylight-pilot/tls/private-key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_session_cache shared:daylight_tls:1m;
        ssl_session_timeout 10m;
        ssl_session_tickets off;
        if ($daylight_origin_ok = 0) { return 444; }
        if ($daylight_backend = "") { return 444; }

        limit_req zone=daylight_requests burst=60 nodelay;
        limit_req_status 429;
        limit_conn daylight_connections 24;
        limit_conn_status 429;
        limit_rate 256k;

        add_header Cache-Control "no-store" always;
        add_header Strict-Transport-Security "max-age=31536000" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;
        add_header Referrer-Policy "no-referrer" always;
        add_header Content-Security-Policy "frame-ancestors 'none'; base-uri 'self'; object-src 'none'" always;

        location / {
            limit_except GET POST { deny all; }
            proxy_pass $daylight_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header Connection "";
            proxy_set_header X-Forwarded-Proto https;
            # Neither caller-controlled forwarding data nor the origin secret
            # is forwarded into application state, archive or diagnostics.
            proxy_set_header X-Forwarded-For "";
            proxy_set_header X-Real-IP "";
            proxy_set_header X-Daylight-Origin-Token "";
            proxy_hide_header Cache-Control;
            proxy_hide_header Expires;
            proxy_hide_header Strict-Transport-Security;
            proxy_buffering off;
            proxy_request_buffering off;
            proxy_cache off;
            proxy_max_temp_file_size 0;
            proxy_connect_timeout 3s;
            proxy_send_timeout 20s;
            proxy_read_timeout 180s;
            proxy_next_upstream off;
        }
    }
}
'''


def run(*args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=30)
    if result.returncode:
        # nginx errors can include config text, so keep them in a private file.
        failure=DIRECTORY/'last-check-error.txt'
        with failure.open('w') as output:
            output.write(result.stdout+result.stderr)
        failure.chmod(0o600)
        raise RuntimeError('Proxy check failed; details remain in the private host error file')
    return result.stdout


def prepare():
    token=private_file(TOKEN).decode('ascii').strip()
    private_file(TLS/'fullchain.pem')
    private_file(TLS/'private-key.pem')
    DIRECTORY.mkdir(mode=0o700,exist_ok=True)
    DIRECTORY.chmod(0o700)
    candidate=render(token).encode()
    if CANDIDATE.exists() and private_file(CANDIDATE)!=candidate:
        raise ValueError('Existing candidate differs; review it before replacement')
    with CANDIDATE.open('wb') as stream:stream.write(candidate)
    CANDIDATE.chmod(0o600)
    # nginx -t checks directories without starting a listener.
    import pwd
    user=pwd.getpwnam('nginx')
    temp=Path('/run/daylight-nginx')
    temp.mkdir(mode=0o700,exist_ok=True);os.chown(temp,user.pw_uid,user.pw_gid)
    for name in ('body','proxy'):
        path=temp/name;path.mkdir(mode=0o700,exist_ok=True);os.chown(path,user.pw_uid,user.pw_gid)
    run(NGINX,'-t','-c',str(CANDIDATE))
    return {'candidate_sha256':hashlib.sha256(candidate).hexdigest(),
            'syntax_checked':True,'started':False,'public_access_changed':False}


def activate(expected):
    candidate=private_file(CANDIDATE)
    if not re.fullmatch('[0-9a-f]{64}',expected) or hashlib.sha256(candidate).hexdigest()!=expected:
        raise ValueError('Candidate does not match the reviewed digest')
    # Revalidate immediately before service configuration. The root-only token
    # must still match; a changed token requires a new reviewed candidate.
    if render(private_file(TOKEN).decode('ascii').strip()).encode()!=candidate:
        raise ValueError('Origin token changed since preparation')
    run(NGINX,'-t','-c',str(CANDIDATE))
    OVERRIDE.parent.mkdir(parents=True,exist_ok=True)
    value='''[Service]
ExecStartPre=
ExecStartPre=+/usr/bin/chown nginx:nginx /run/daylight-nginx
ExecStartPre=/usr/sbin/nginx -t -c /etc/daylight-pilot/proxy/nginx.conf
ExecStart=
ExecStart=/usr/sbin/nginx -c /etc/daylight-pilot/proxy/nginx.conf
ExecReload=
ExecReload=/usr/sbin/nginx -s reload -c /etc/daylight-pilot/proxy/nginx.conf
RuntimeDirectory=daylight-nginx
RuntimeDirectoryMode=0700
LimitNOFILE=1024
MemoryMax=192M
TasksMax=16
StandardOutput=null
StandardError=null
'''
    if OVERRIDE.exists() and OVERRIDE.read_text()!=value:
        raise ValueError('Existing nginx override differs; do not overwrite it')
    OVERRIDE.write_text(value);OVERRIDE.chmod(0o644)
    run('systemctl','daemon-reload')
    run('systemctl','enable','nginx')
    run('systemctl','restart','nginx')
    run('systemctl','is-active','--quiet','nginx')
    return {'candidate_sha256':expected,'nginx_active':True,'aws_or_dns_changed':False}


def check():
    """Loopback HTTPS admission checks only: no invitation, turn or provider call."""
    token=private_file(TOKEN).decode('ascii').strip()
    context=ssl.create_default_context()
    results=[]
    for host,path,authorized,expected in (
            ('daylightmedicare.com','/pilot/join',True,200),
            ('test.daylightmedicare.com','/pilot/join',True,200),
            ('daylightmedicare.com','/api/guest/session',True,401),
            ('test.daylightmedicare.com','/api/guest/session',True,401),
            ('daylightmedicare.com','/pilot/join',False,444),
            ('unknown.example','/pilot/join',True,444)):
        with socket.create_connection(('127.0.0.1',443),timeout=5) as tcp:
            with context.wrap_socket(tcp,server_hostname='origin.daylightmedicare.com') as tls:
                headers={'Host':host,'Origin':'https://'+host,'Connection':'close'}
                if authorized:headers['X-Daylight-Origin-Token']=token
                request='GET '+path+' HTTP/1.1\r\n'+''.join(k+': '+v+'\r\n' for k,v in headers.items())+'\r\n'
                tls.sendall(request.encode())
                response=http.client.HTTPResponse(tls)
                try:response.begin()
                except (http.client.RemoteDisconnected, ConnectionResetError):
                    if expected!=444:raise RuntimeError('Expected private origin response was unavailable') from None
                    status=444
                else:
                    status=response.status
                    if status!=expected:raise RuntimeError('Private origin admission check failed')
                    if 'no-store' not in (response.getheader('Cache-Control') or ''):
                        raise RuntimeError('Private responses must not be cached')
                    if not response.getheader('Strict-Transport-Security'):
                        raise RuntimeError('Missing HTTPS security header')
                    response.read(100000)
                results.append({'host':host,'path':path,'authorized_origin':authorized,'status':status})
    return {'tls_chain_and_hostname_verified':True,'admission_checks':results,'provider_calls':0}


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare')
    sub.add_parser('check')
    live=sub.add_parser('activate')
    live.add_argument('sha256')
    live.add_argument('--approved-runtime-access',action='store_true',required=True)
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Root administration is required')
    result=prepare() if args.command=='prepare' else check() if args.command=='check' else activate(args.sha256)
    print(json.dumps(result))


if __name__=='__main__':main()
