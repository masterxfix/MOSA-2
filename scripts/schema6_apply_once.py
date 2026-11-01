"""Single manual run, existing pinned tunnel; no remote files or provider access."""
import json
import logging
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import collector_actions as access

EXECUTION = 'MOSA2-SCHEMA6-20261101-01'

def guard(env):
    expected = {'GITHUB_REPOSITORY': 'masterxfix/MOSA-2', 'GITHUB_REF': 'refs/heads/main',
                'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_ATTEMPT': '1',
                'GITHUB_RUN_NUMBER': '1', 'EXECUTION_ID': EXECUTION}
    if any(env.get(k) != v for k, v in expected.items()):
        raise ValueError('RUN_GUARD')
    sha = env.get('GITHUB_SHA', '')
    if not re.fullmatch('[0-9a-f]{40}', sha) or env.get('EXPECTED_COMMIT') != sha:
        raise ValueError('COMMIT_GUARD')
    if env.get('AUTHORIZATION') != EXECUTION + ':' + sha:
        raise ValueError('AUTHORIZATION_GUARD')

def no_other_runs(env, get=None):
    def fetch(status):
        req = urllib.request.Request('https://api.github.com/repos/masterxfix/MOSA-2/actions/runs?per_page=100&status=' + status,
            headers={'Authorization': 'Bearer ' + env['GH_TOKEN'], 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)
    for status in ('queued', 'in_progress', 'waiting', 'pending', 'requested'):
        result = (get or fetch)(status)
        if result['total_count'] > 100 or any(str(r['id']) != env['GITHUB_RUN_ID'] for r in result['workflow_runs']):
            raise ValueError('OTHER_ACTIONS_ACTIVE')

def validated_output(raw):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='strict')
    if len(raw) > 32768:
        raise ValueError('OUTPUT_BOUND')
    events = []
    for line in raw.splitlines():
        obj = json.loads(line)
        stage = obj.get('stage', '')
        if not re.fullmatch(r'(PREFLIGHT_PASS|DDL[56]_[1-5]_(START|CONFIRMED)|BOOTSTRAP5_(START|CONFIRMED)|LEDGER6_(START|CONFIRMED)|SCHEMA[56]_PASS|SUCCESS|STOP)', stage):
            raise ValueError('OUTPUT_STAGE')
        events.append(obj)
    return events

def execute(env):
    stage = 'GUARDS'
    try:
        guard(env)
        no_other_runs(env)
        config = access.configuration(env)
        import paramiko
        logging.getLogger('paramiko').disabled = True
        stage = 'SSH'
        with access.ssh_client(config, {}, paramiko) as transport:
            stage = 'TUNNEL'
            with access.tunnel(transport, {}) as port:
                request = dict(password=env['MOSA_TEST_DB_PASSWORD'], port=port,
                    execution=EXECUTION, attempt=env['GITHUB_RUN_ATTEMPT'],
                    run_number=env['GITHUB_RUN_NUMBER'], commit=env['GITHUB_SHA'])
                child = {k: env[k] for k in ('PATH', 'HOME', 'LANG') if k in env}
                stage = 'APPLY_PROCESS'
                try:
                    result = subprocess.run(['php', str(ROOT / 'scripts/schema6_apply.php')],
                        input=json.dumps(request), text=True, capture_output=True, env=child,
                        cwd=ROOT, timeout=600)
                except subprocess.TimeoutExpired as error:
                    events = validated_output(error.stdout or '')
                    return dict(ok=False, outcome='PARTIAL_OR_UNKNOWN', stage='PROCESS_TIMEOUT', events=events)
                if result.stderr:
                    raise ValueError('STDERR_REJECTED')
                events = validated_output(result.stdout)
                return dict(ok=result.returncode == 0 and bool(events) and events[-1]['stage'] == 'SUCCESS',
                            stage='FINISHED', execution=EXECUTION, commit=env['GITHUB_SHA'], events=events)
    except Exception:
        return dict(ok=False, stage=stage, outcome='PARTIAL_OR_UNKNOWN' if stage == 'APPLY_PROCESS' else 'NO_SCHEMA_WRITES')

if __name__ == '__main__':
    report = execute(os.environ)
    encoded = access.public_text(report, os.environ)
    print(encoded)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as out:
            out.write('Schema 6 one-time Dogado apply\n\n```json\n' + encoded + '\n```\n')
    sys.exit(0 if json.loads(encoded).get('ok') else 1)
