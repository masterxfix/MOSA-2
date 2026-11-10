"""Manual collector runner with the existing pinned Dogado SSH boundary."""
from contextlib import contextmanager
import json
import hashlib
import logging
import os
from pathlib import Path
import select
import socketserver
import subprocess
import sys
import tempfile
import threading

import deploy_test_sftp as profile
import deploy_sftp as shared

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ('MOSA_TEST_SFTP_PASSWORD', 'MOSA_TEST_SFTP_HOST_KEY_SHA256', 'MOSA_TEST_DB_PASSWORD')


class ConfigurationError(ValueError):
    pass


def configuration(env):
    # Name-only diagnostics. Never interpolate a configuration value into errors.
    for name in SECRETS:
        if not env.get(name):
            raise ConfigurationError('MISSING_SECRET: ' + name)
    for suffix, expected in profile.EXPECTED.items():
        name = profile.PREFIX + suffix
        if not env.get(name):
            raise ConfigurationError('MISSING_VARIABLE: ' + name)
        if env[name] != expected:
            raise ConfigurationError('INVALID_VARIABLE: ' + name)
    try:
        return profile.configuration(env)
    except ValueError:
        raise ConfigurationError('INVALID_HOST_KEY_CONFIGURATION') from None


@contextmanager
def ssh_client(config, status, paramiko):
    class PinnedKey(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            status['host_key'] = 'FAIL'
            shared.verify_fingerprint(key.asbytes(), config['host_key_sha256'])
            status['host_key'] = 'PASS'

    client = paramiko.SSHClient()
    try:
        client.set_missing_host_key_policy(PinnedKey())
        client.connect(config['host'], port=22, username=config['user'],
                       password=config['password'], allow_agent=False, look_for_keys=False,
                       timeout=20, banner_timeout=20, auth_timeout=20, channel_timeout=30,
                       disabled_algorithms={'keys': ['ssh-rsa', 'rsa-sha2-256', 'rsa-sha2-512',
                           'ecdsa-sha2-nistp256', 'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521']})
        status['ssh'] = 'PASS'
        yield client.get_transport()
    finally:
        client.close()


@contextmanager
def tunnel(transport, status):
    # Explicit pre-provider forwarding test, then a loopback-only ephemeral listener.
    probe = transport.open_channel('direct-tcpip', ('127.0.0.1', 3307), ('127.0.0.1', 0), timeout=15)
    probe.close()
    status['db_tunnel'] = 'PASS'

    class Forward(socketserver.BaseRequestHandler):
        def handle(self):
            channel = None
            try:
                channel = transport.open_channel('direct-tcpip', ('127.0.0.1', 3307), self.client_address, timeout=15)
                while True:
                    ready, _, _ = select.select([self.request, channel], [], [], 30)
                    if not ready:
                        if not transport.is_active():
                            break
                        continue
                    if self.request in ready:
                        data = self.request.recv(65536)
                        if not data:
                            break
                        channel.sendall(data)
                    if channel in ready:
                        data = channel.recv(65536)
                        if not data:
                            break
                        self.request.sendall(data)
            except Exception:
                # Authentication/target validation by PDO determines success. No thread trace.
                pass
            finally:
                if channel is not None:
                    channel.close()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = False

    with Server(('127.0.0.1', 0), Forward) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_address[1]
        finally:
            server.shutdown()
            thread.join(timeout=5)


def invoke_acceptance(port, private, env, run=subprocess.run):
    config = dict(python=sys.executable, php='php', project=str(ROOT), runtime_path=env.get('PATH', ''),
                  public_root=str(ROOT), db_host='127.0.0.1', db_port=port,
                  request_script=str(ROOT/'scripts/market_collector/frankfurt_request.php'),
                  state_contract=dict(schema_version=4, allow_current=True))
    wire = dict(password=env['MOSA_TEST_DB_PASSWORD'], private_root=private, config=config)
    # Secret only on stdin; child environment omits all Actions and SSH credentials.
    child_env = {k: env[k] for k in ('PATH', 'HOME', 'LANG', 'SYSTEMROOT', 'TEMP', 'TMP') if k in env}
    child_env['PYTHONDONTWRITEBYTECODE'] = '1'
    reply = run(['php', str(ROOT/'scripts/market_collector/actions_acceptance.php')],
                input=json.dumps(wire), text=True, capture_output=True, cwd=ROOT, env=child_env, timeout=480)
    if reply.returncode != 0 or reply.stderr:
        raise RuntimeError('COLLECTOR_PROCESS_FAILED')
    result = json.loads(reply.stdout)
    if not isinstance(result, dict) or type(result.get('ok')) is not bool:
        raise RuntimeError('COLLECTOR_RESULT_INVALID')
    return result


def public_text(report, env):
    encoded = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2)
    for name in SECRETS:
        value = env.get(name)
        if value and (value in encoded or json.dumps(value)[1:-1] in encoded):
            # Suppress the entire result, not just a fragment or transformed secret.
            return json.dumps(dict(ok=False, failure='SECRET_OUTPUT_BLOCKED', secrets_in_log='NEIN/PASS'))
    return encoded


def execute(env, paramiko=None):
    report = dict(ok=False, stage='configuration', ssh='NOT_CHECKED', host_key='NOT_CHECKED',
                  db_tunnel='NOT_CHECKED', db_authentication='NOT_CHECKED',
                  preparation_provider_requests=0, final_provider_requests=0,
                  batch_status='NOT_STARTED', secrets_in_log='NEIN/PASS', acceptance=None)
    try:
        config = configuration(env)
        if paramiko is None:
            import paramiko
        logging.getLogger('paramiko').disabled = True
        logging.getLogger('paramiko').addHandler(logging.NullHandler())
        logging.getLogger('paramiko').propagate = False
        report['stage'] = 'ssh'
        with ssh_client(config, report, paramiko) as transport:
            report['stage'] = 'db_tunnel'
            with tunnel(transport, report) as port:
                report['stage'] = 'acceptance'
                # Private runner-only files, deleted on success and every exception path.
                with tempfile.TemporaryDirectory(prefix='mosa2-collector-') as private:
                    os.chmod(private, 0o700)
                    report['acceptance'] = invoke_acceptance(port, private, env)
                    report['ok'] = report['acceptance']['ok']
                    report['db_authentication'] = report['acceptance']['db_authentication']
                    report['preparation_provider_requests'] = report['acceptance']['preparation_provider_requests']
                    batch = report['acceptance']['batch']
                    if batch is not None:
                        report['final_provider_requests'] = batch['provider_requests']
                        report['batch_status'] = batch['overall_status']
        report['stage'] = 'finished'
    except ConfigurationError as error:
        report['failure'] = str(error)  # Controlled names-only diagnostics.
    except Exception as error:
        report['failure_type'] = type(error).__name__  # Never exception text or captured stderr.
        if report['stage'] in ('ssh', 'db_tunnel'):
            report[report['stage']] = 'FAIL'
    return report


def main():
    report = execute_collection(os.environ) if '--collection' in sys.argv else execute(os.environ)
    encoded = public_text(report, os.environ)
    print(encoded)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as output:
            output.write('MOSA-2 manual collector acceptance\n\n```json\n' + encoded + '\n```\n')
    return 0 if report['ok'] and json.loads(encoded).get('ok') else 1


def collection_scope(env):
    commit = env.get('MOSA_MARKET_EXPECTED_COMMIT', '')
    import re
    if (not re.fullmatch('[0-9a-f]{40}', commit) or env.get('GITHUB_SHA') != commit
            or env.get('GITHUB_ACTIONS') != 'true' or env.get('GITHUB_RUN_ATTEMPT') != '1'
            or env.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or env.get('GITHUB_REF') not in ('refs/heads/main','refs/heads/codex/issue-59-24h-quotes')
            or env.get('GITHUB_REPOSITORY') != 'masterxfix/MOSA-2'):
        raise ConfigurationError('COLLECTION_CONTEXT')
    raw = env.get('MOSA_MARKET_SCOPE', '')
    scope = json.loads(raw)
    required = {'mode', 'request_budget', 'source_priority', 'expected_isins'}
    if (type(scope) is not dict or set(scope) not in (required, required | {'archive'})
            or scope['mode'] != 'manual' or type(scope['request_budget']) is not int
            or not 1 <= scope['request_budget'] <= 5
            or type(scope['expected_isins']) is not list
            or not 1 <= len(scope['expected_isins']) <= scope['request_budget']
            or any(not isinstance(i, str) or not re.fullmatch('[A-Z]{2}[A-Z0-9]{9}[0-9]', i) for i in scope['expected_isins'])
            or len(set(scope['expected_isins'])) != len(scope['expected_isins'])
            or type(scope['source_priority']) is not list or not scope['source_priority']
            or any(s not in ('provider:tradegate_bsx_mid', 'provider:boerse_frankfurt_api', 'provider:gettex_mund_delayed') for s in scope['source_priority'])
            or len(set(scope['source_priority'])) != len(scope['source_priority'])):
        raise ConfigurationError('COLLECTION_SCOPE')
    archive = scope.get('archive')
    gettex = 'provider:gettex_mund_delayed' in scope['source_priority']
    if gettex or 'archive' in scope:
        if (env.get('MOSA_MARKET_GETTEX_PRIVATE_USE') != '1' or scope['request_budget'] != 1
                or scope['source_priority'] != ['provider:gettex_mund_delayed']
                or type(archive) is not dict or set(archive) != {'slot','sha256'}
                or not isinstance(archive['slot'],str) or not re.fullmatch(r'[0-9]{8}\.[0-9]{2}\.[0-9]{2}',archive['slot'])
                or not isinstance(archive['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',archive['sha256'])):
            raise ConfigurationError('GETTEX_PRIVATE_USE_OR_BUDGET')
    elif env.get('GITHUB_REF') != 'refs/heads/main':
        raise ConfigurationError('COLLECTION_CONTEXT')
    digest = hashlib.sha256(raw.encode()).hexdigest()
    if env.get('MOSA_MARKET_AUTHORIZATION') != 'MOSA2-MARKET-BATCH:' + commit + ':' + digest:
        raise ConfigurationError('COLLECTION_AUTHORIZATION')
    return scope


def execute_collection(env, paramiko=None):
    report = dict(ok=False, stage='configuration', provider_requests=0)
    try:
        scope = collection_scope(env)
        config = configuration(env)
        if paramiko is None:
            import paramiko
        report['stage'] = 'ssh'
        with ssh_client(config, report, paramiko) as transport:
            if 'archive' in scope:
                sys.path.insert(0,str(ROOT))
                from scripts.market_collector import dogado_archive
                report['stage'] = 'collection'
                result = dogado_archive.execute(transport,ROOT,scope,env['MOSA_TEST_DB_PASSWORD'])
                report.update(ok=result.get('ok') is True,collection=result,provider_requests=result.get('provider_requests'))
                return report
            report['stage'] = 'db_tunnel'
            with tunnel(transport, report) as port:
                with tempfile.TemporaryDirectory(prefix='mosa2-market-batch-') as private:
                    os.chmod(private, 0o700)
                    runtime = dict(python=sys.executable, php='php', project=str(ROOT), runtime_path=env.get('PATH', ''),
                        public_root=str(ROOT), db_host='127.0.0.1', db_port=port,
                        request_script=str(ROOT/'scripts/market_collector/frankfurt_request.php'),
                        state_contract=dict(schema_version=6, allow_current=True))
                    wire = dict(password=env['MOSA_TEST_DB_PASSWORD'], config=runtime, scope=scope, private_root=private)
                    child_env = {k: env[k] for k in ('PATH','HOME','LANG','SYSTEMROOT','TEMP','TMP') if k in env}
                    child_env['PYTHONDONTWRITEBYTECODE'] = '1'
                    report['stage'] = 'collection'
                    reply = subprocess.run(['php', str(ROOT/'scripts/market_collector/live_batch.php')],
                        input=json.dumps(wire), text=True, capture_output=True, cwd=ROOT, env=child_env, timeout=600)
                    if reply.stderr:
                        raise RuntimeError('COLLECTION_PROCESS_FAILED')
                    result = json.loads(reply.stdout)
                    report['collection'] = result
                    report['provider_requests'] = result.get('provider_requests')
                    report['ok'] = reply.returncode == 0 and result.get('ok') is True
    except ConfigurationError as error:
        report['failure'] = str(error)
    except Exception as error:
        report['failure_type'] = type(error).__name__
        if report['stage'] == 'collection':
            report['provider_requests'] = None  # Unknown output never means zero requests/writes.
    return report


if __name__ == '__main__':
    sys.exit(main())
