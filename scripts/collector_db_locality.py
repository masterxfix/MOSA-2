"""Bounded, fileless PHP locality measurement using the existing pinned SSH profile."""
import hashlib
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import collector_actions as shared

ROOT = Path(__file__).resolve().parents[1]
PHP_CANDIDATES = ('/opt/plesk/php/8.4/bin/php', '/usr/bin/php', 'php')
PHP_FLAGS = ('-d', 'display_errors=0', '-d', 'log_errors=0', '-d', 'auto_prepend_file=',
             '-d', 'auto_append_file=', '-d', 'opcache.enable_cli=0', '-d', 'opcache.file_cache=')
BOOTSTRAP = '$mosa_input=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);eval($mosa_input["source"]);'
CAPABILITY = ('echo json_encode(array("version"=>PHP_VERSION,"version_id"=>PHP_VERSION_ID,'
              '"sapi"=>PHP_SAPI,"pdo_mysql"=>class_exists("PDO")&&in_array("mysql",PDO::getAvailableDrivers(),true)));')
MAX_OUTPUT = 65536


class ProbeError(RuntimeError):
    pass


def source():
    text = (ROOT/'scripts/market_collector/db_locality_probe.php').read_text(encoding='utf-8')
    if not text.startswith('<?php\n'):
        raise ProbeError('PROBE_SOURCE_INVALID')
    return text[len('<?php\n'):]


def command(binary, code):
    if binary not in PHP_CANDIDATES:
        raise ProbeError('UNAPPROVED_PHP_COMMAND')
    return shlex.join([binary, *PHP_FLAGS, '-r', code])


def remote_call(transport, cmd, payload=b'', timeout=90):
    """No PTY, environment request, shell file operation or SFTP. Never publish stderr."""
    started = time.monotonic()
    try:
        channel = transport.open_session(timeout=15)
    except Exception:
        raise ProbeError('SSH_SESSION_CHANNEL_REJECTED') from None
    try:
        channel.settimeout(20)
        try:
            channel.exec_command(cmd)
        except Exception:
            raise ProbeError('SSH_EXEC_REQUEST_REJECTED') from None
        if payload:
            channel.sendall(payload)
        channel.shutdown_write()
        output = bytearray()
        stderr_bytes = 0
        while True:
            if time.monotonic()-started > timeout:
                raise ProbeError('SSH_COMMAND_TIMEOUT')
            while channel.recv_ready():
                output.extend(channel.recv(4096))
                if len(output) > MAX_OUTPUT:
                    raise ProbeError('SSH_OUTPUT_LIMIT')
            while channel.recv_stderr_ready():
                stderr_bytes += len(channel.recv_stderr(4096))
                if stderr_bytes > MAX_OUTPUT:
                    raise ProbeError('SSH_STDERR_LIMIT')
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                break
            time.sleep(0.01)
        return channel.recv_exit_status(), bytes(output), bool(stderr_bytes), (time.monotonic()-started)*1000
    finally:
        channel.close()


def capability(transport, attempts=None):
    if attempts is None:
        attempts = []
    for binary in PHP_CANDIDATES:
        code, output, errors, elapsed = remote_call(transport, command(binary, CAPABILITY), timeout=25)
        result = None
        if code == 0 and not errors:
            try:
                candidate = json.loads(output)
                if (isinstance(candidate, dict) and type(candidate.get('version_id')) is int
                        and isinstance(candidate.get('version'), str) and len(candidate['version']) < 40
                        and candidate.get('sapi') == 'cli' and type(candidate.get('pdo_mysql')) is bool):
                    result = candidate
            except (ValueError, TypeError):
                pass
        attempts.append(dict(command=binary, exit_code=code, valid_capability=result, stderr_suppressed=errors))
        if result and 80400 <= result['version_id'] < 80500 and result['pdo_mysql']:
            return binary, attempts
    raise ProbeError('NO_PHP84_CLI_WITH_PDO_MYSQL_IN_APPROVED_COMMANDS')


def payload(port, env, php_source):
    return json.dumps(dict(port=port, password=env['MOSA_TEST_DB_PASSWORD'], source=php_source)).encode('utf-8')


def local_probe(port, env, php_source):
    child_env = {key: env[key] for key in ('PATH', 'HOME', 'LANG') if key in env}
    child_env['PYTHONDONTWRITEBYTECODE'] = '1'
    args = ['php', *PHP_FLAGS, '-r', BOOTSTRAP]
    started = time.monotonic()
    process = subprocess.run(args, input=payload(port, env, php_source), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=ROOT, env=child_env, timeout=90, check=False)
    if process.returncode or process.stderr or len(process.stdout) > MAX_OUTPUT:
        raise ProbeError('A_PHP_PROCESS_FAILED')
    try:
        report = json.loads(process.stdout)
    except (ValueError, TypeError):
        raise ProbeError('A_PHP_OUTPUT_INVALID') from None
    report['process_elapsed_ms'] = (time.monotonic()-started)*1000
    return report


def ratios(a, b):
    out = {}
    for key, va, vb in [('pdo_connect', a['pdo_connect_ms'], b['pdo_connect_ms']),
                         ('all_selects', a['all_selects']['mean_ms'], b['all_selects']['mean_ms']),
                         ('direct', a['direct']['mean_ms'], b['direct']['mean_ms']),
                         ('native', a['native']['mean_ms'], b['native']['mean_ms']),
                         ('total_sequence', a['total_sequence_ms'], b['total_sequence_ms'])]:
        if va <= 0 or vb <= 0:
            raise ProbeError('NON_POSITIVE_TIMING')
        out[key] = dict(tunnel_over_local=va/vb, reduction_percent=100*(1-vb/va))
    return out


def execute(env, paramiko=None):
    report = dict(ok=False, stage='configuration', provider_requests=0, business_writes=0,
                  ssh='NOT_CHECKED', host_key='NOT_CHECKED', db_tunnel='NOT_CHECKED',
                  dogado_php84_cli='NOT_CHECKED', dogado_pdo_mysql='NOT_CHECKED', dogado_local_db='NOT_CHECKED')
    try:
        config = shared.configuration(env)
        php_source = source()
        report['probe_source_sha256'] = hashlib.sha256(php_source.encode('utf-8')).hexdigest()
        if paramiko is None:
            import paramiko
        logging.getLogger('paramiko').disabled = True
        report['stage'] = 'ssh'
        with shared.ssh_client(config, report, paramiko) as transport:
            report['stage'] = 'dogado_cli_capability'
            report['capability_attempts'] = []
            binary, attempts = capability(transport, report['capability_attempts'])
            report['dogado_php84_cli'] = 'PASS'
            report['dogado_pdo_mysql'] = 'PASS'
            print('MOSA locality: approved Dogado PHP 8.4 CLI and PDO MySQL available', flush=True)
            report['stage'] = 'A_tunnel'
            with shared.tunnel(transport, report) as port:
                a = local_probe(port, env, php_source)
                report['A'] = a
                if not a.get('ok'):
                    raise ProbeError('A_READONLY_PROBE_FAILED')
            report['stage'] = 'B_local'
            code, output, errors, elapsed = remote_call(transport, command(binary, BOOTSTRAP),
                                                        payload(3307, env, php_source))
            if code or errors:
                raise ProbeError('B_PHP_PROCESS_FAILED')
            try:
                b = json.loads(output)
            except (ValueError, TypeError):
                raise ProbeError('B_PHP_OUTPUT_INVALID') from None
            b['process_elapsed_ms'] = elapsed
            report['B'] = b
            if not b.get('ok'):
                raise ProbeError('B_READONLY_PROBE_FAILED')
            report['dogado_local_db'] = 'PASS'
            if a['pdo_config'] != b['pdo_config'] or a['select1_executions'] != 10 or b['select1_executions'] != 10:
                raise ProbeError('A_B_CONTRACT_MISMATCH')
            report['comparison'] = ratios(a, b)
            report['ok'] = True
        report['stage'] = 'finished'
    except shared.ConfigurationError as error:
        report['failure'] = str(error)
    except ProbeError as error:
        report['failure'] = str(error)
        if report['stage'] == 'dogado_cli_capability':
            found84 = any(a.get('valid_capability') and 80400 <= a['valid_capability']['version_id'] < 80500
                          for a in report.get('capability_attempts', []))
            report['dogado_php84_cli'] = 'PASS' if found84 else 'FAIL'
            report['dogado_pdo_mysql'] = 'FAIL' if found84 else 'NOT_CHECKED'
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
            stream.write('MOSA-2 DB locality probe\n\n'+fence+'json\n'+encoded+'\n'+fence+'\n')
    return 0 if report['ok'] and json.loads(encoded).get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
