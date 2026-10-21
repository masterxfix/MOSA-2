"""Manual read-only diagnostics; reuses the existing fixed profile and SSH tunnel."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import collector_actions as shared

ROOT = Path(__file__).resolve().parents[1]


def php_diagnostic(port, env):
    config = dict(python=sys.executable, php='php', project=str(ROOT), runtime_path=env.get('PATH', ''),
                  compare_runtime='--compare-runtime' in sys.argv, db_host='127.0.0.1', db_port=port, state_contract=dict(schema_version=4, allow_current=True))
    child_env = {key: env[key] for key in ('PATH', 'HOME', 'LANG') if key in env}
    child_env['PYTHONDONTWRITEBYTECODE'] = '1'
    command = ['php', str(ROOT/'scripts/market_collector/performance_diagnostic.php')]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, cwd=ROOT, env=child_env) as child:
        timer = threading.Timer(540, child.kill)
        timer.start()
        errors = []
        drain = threading.Thread(target=lambda: errors.append(bool(child.stderr.read())), daemon=True)
        drain.start()
        result = None
        try:
            child.stdin.write(json.dumps(dict(password=env['MOSA_TEST_DB_PASSWORD'], config=config)))
            child.stdin.close()
            for line in child.stdout:
                record = json.loads(line)
                if record.get('event') == 'progress':
                    public = dict(event='progress', phase=record['phase'], isin=record.get('isin'))
                    print(shared.public_text(public, env), flush=True)
                elif record.get('event') == 'result':
                    result = record['report']
                else:
                    raise RuntimeError('DIAGNOSTIC_OUTPUT_INVALID')
            code = child.wait()
            drain.join(timeout=5)
            if code != 0 or any(errors) or not isinstance(result, dict):
                raise RuntimeError('DIAGNOSTIC_PROCESS_FAILED')
            return result
        finally:
            timer.cancel()


def execute(env):
    report = dict(ok=False, stage='configuration', provider_requests=0, business_writes=0,
                  ssh='NOT_CHECKED', host_key='NOT_CHECKED', db_tunnel='NOT_CHECKED')
    try:
        config = shared.configuration(env)
        import paramiko
        logging.getLogger('paramiko').addHandler(logging.NullHandler())
        logging.getLogger('paramiko').propagate = False
        report['stage'] = 'ssh'
        started = time.perf_counter()
        with shared.ssh_client(config, report, paramiko) as transport:
            report['ssh_connect_auth_ms'] = (time.perf_counter()-started)*1000
            print(json.dumps(dict(event='progress', phase='ssh_complete',
                                 duration_ms=report['ssh_connect_auth_ms'])), flush=True)
            report['stage'] = 'tunnel'
            started = time.perf_counter()
            with shared.tunnel(transport, report) as port:
                report['tunnel_probe_listener_ms'] = (time.perf_counter()-started)*1000
                report['stage'] = 'readonly_diagnostic'
                report['diagnostic'] = php_diagnostic(port, env)
                report['ok'] = report['diagnostic']['ok']
        report['stage'] = 'finished'
    except shared.ConfigurationError as error:
        report['failure'] = str(error)
    except Exception as error:
        report['failure_type'] = type(error).__name__
    report['secrets_in_log'] = 'NEIN/PASS'
    return report


def main():
    report = execute(os.environ)
    encoded = shared.public_text(report, os.environ)
    print(encoded, flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            fence = chr(96)*3
            stream.write('MOSA-2 read-only performance diagnosis\n\n'+fence+'json\n'+encoded+'\n'+fence+'\n')
    return 0 if report['ok'] and json.loads(encoded).get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
