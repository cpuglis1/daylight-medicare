#!/usr/bin/env python3
"""Root-only, read-only D199 host checks. Never reads keys, cookies or chat rows."""
import argparse
import ast
import hashlib
import http.client
import json
import os
from pathlib import Path
import sqlite3
import subprocess

RELEASE = '99b3717656116a08a192148711bc8acb12d37f7664fc0e916bf3fa0a7ca41c22'
BASE = 'c7cec20f91e8a92e6164463d293362f83464c453fcdd460ed5b00c742063feeb'
LEDGER = '/var/lib/daylight-state/budget/model-usage.sqlite3'
stage = 'arguments'


def require(condition):
    if not condition:
        raise ValueError('verification failed')


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=15).strip()


def ledger_snapshot():
    with sqlite3.connect('file:' + LEDGER + '?mode=ro', uri=True) as db:
        return db.execute('SELECT count(*),coalesce(sum(charged),0),coalesce(sum(measured),0) FROM ai_charges').fetchone()


def source_checks(app):
    """Inspect constants without importing/initializing any application code."""
    tree = ast.parse((app / 'hosted_server.py').read_text())
    require(any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MODEL' for t in n.targets)
                and isinstance(n.value, ast.Constant) and n.value.value == 'gpt-6.1-sol' for n in tree.body))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'ResponsesClient']
    require(bool(calls) and all(any(k.arg == 'reasoning_effort' and isinstance(k.value, ast.Constant)
                and k.value.value == 'low' for k in n.keywords) for n in calls))
    budget = ast.parse((app / 'pilot_budget.py').read_text())
    cls = next(n for n in budget.body if isinstance(n, ast.ClassDef) and n.name == 'PilotBudget')
    cap = next(n.value for n in cls.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == 'invite_cap' for t in n.targets))
    daily = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'daily_cap_nano_usd')
    require(ast.unparse(cap) == '2 * NANO')
    require(any(isinstance(n, ast.Return) and ast.unparse(n.value) == '20 * NANO' for n in daily.body))


def main():
    global stage
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checks-environment', choices=('test', 'pilot'), required=True)
    target = parser.parse_args().checks_environment
    require(os.geteuid() == 0)
    stage = 'ledger before'
    before = ledger_snapshot()
    results = []
    for env, port, host in [('test', 19094, 'test.daylightmedicare.com'), ('pilot', 19093, 'daylightmedicare.com')]:
        stage = env + ': config and process'
        unit = 'daylight-' + env + '.service'
        config_path = Path('/etc/daylight-pilot/runtime') / (env + '.json')
        cfg = json.loads(config_path.read_text())
        release = cfg['release']
        require(release == RELEASE if env == target or target == 'pilot' else release in (BASE, RELEASE))
        require(cfg['ledger'] == LEDGER and cfg['key_file'] == '/run/credentials/' + unit + '/openai')
        require(cfg['environment'] == env and cfg['port'] == port)
        root = Path('/opt/daylight-pilot/releases') / release
        require(hashlib.sha256((root / 'release-manifest.json').read_bytes()).hexdigest() == release)
        require(command('systemctl', 'is-active', unit) == 'active')
        pid = int(command('systemctl', 'show', unit, '--property=MainPID', '--value'))
        require(pid > 0)
        args = Path('/proc/' + str(pid) + '/cmdline').read_bytes().split(b'\0')
        require(str(root / 'alternatives/advisor-first/hosted_server.py').encode() in args)
        require(str(config_path).encode() in args and b'--paused' not in args)
        process_env = dict(x.split(b'=', 1) for x in Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0') if b'=' in x)
        require(process_env.get(b'DAYLIGHT_MODEL_ENVIRONMENT') == b'hosted-demo')
        checks = all(k in cfg for k in ('foundation_binding', 'foundation_root', 'foundation_dsn', 'controls_dsn'))
        require(checks == (env == target))
        if release == RELEASE:
            for key, value in {'DAYLIGHT_BLOCK_RELEASE':'on', 'DAYLIGHT_TOKEN_PREFLIGHT':'local_bound',
                               'DAYLIGHT_REVEAL_WPS':'20', 'DAYLIGHT_PRICING_REVIEW':'/etc/daylight-pilot/pricing-review.json'}.items():
                require(process_env.get(key.encode()) == value.encode())
        require(int(command('systemctl', 'show', unit, '--property=MemoryMax', '--value')) == (2 * 1024**3 if checks else 900 * 1024**2))
        if checks:
            require(Path(cfg['foundation_binding']).is_file() and Path(cfg['foundation_root']).is_dir())
        stage = env + ': model and budget source'
        source_checks(root / 'alternatives/advisor-first')
        stage = env + ': unauthenticated loopback HTTP'
        http_results = []
        for path, status, headers in [('/pilot/join', 200, {}), ('/', 303, {}), ('/pilot/access', 200, {}),
                ('/api/status', 401, {}), ('/api/enrollment/content', 401, {}),
                ('/pilot/access', 403, {'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'cors','Sec-Fetch-Dest':'empty'})]:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            conn.request('GET', path, headers={'Host':host, 'Connection':'close', **headers})
            response = conn.getresponse()
            body = response.read(100000)
            require(response.status == status and response.getheader('X-Daylight-Release') == release)
            if path == '/' and status == 303:
                require(response.getheader('Location') == '/pilot/join')
            if path == '/pilot/access' and status == 200:
                require(json.loads(body)['active'] is False)
            http_results.append({'path':path, 'status':response.status})
            conn.close()
        stage = env + ': archive schema permissions'
        query = "SELECT c.relrowsecurity,c.relforcerowsecurity,has_table_privilege('daylight_app','hosted_history.turn_blocks','SELECT'),has_table_privilege('daylight_app','hosted_history.turn_blocks','INSERT'),has_column_privilege('daylight_app','hosted_history.turn_blocks','blocks','UPDATE'),has_table_privilege('daylight_app','hosted_history.turn_blocks','DELETE') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='hosted_history' AND c.relname='turn_blocks'"
        require(command('runuser', '-u', 'postgres', '--', 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
                '-h', '/var/lib/daylight-state/pgsocket', '-p', '55485', '-d', 'daylight_history_' + env, '-c', query) == 't|t|t|t|t|f')
        results.append({'environment':env, 'release':release, 'checks_bound':checks, 'loaded_process_verified':True,
                        'model':'gpt-6.1-sol', 'reasoning':'low', 'caps_usd':[2,20], 'block_schema_verified':True, 'http':http_results})
    stage = 'ledger after'
    print(json.dumps({'ok':True, 'services':results, 'ledger_unchanged_during_check':before == ledger_snapshot(),
                      'provider_calls':0, 'invitation_redemptions':0, 'authenticated_ui_checked':False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'ok':False, 'failed_check':stage, 'provider_calls':0, 'invitation_redemptions':0}))
        raise SystemExit(1)
