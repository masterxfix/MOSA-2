"""One bounded, read-only Dogado market coverage report; no provider or DB writes."""
import json
import logging
import re
from pathlib import Path
import sys

# This script is directly executable from the repository root.  Its shared
# helpers live one directory above this file and must be importable on Linux
# as well as Windows without relying on the caller's working directory.
SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import collector_actions as shared
import collector_db_locality as remote
import deploy_test_sftp as profile

ROOT = Path(__file__).resolve().parents[2]


def source():
    selection = (ROOT / 'scripts/market_collector/selection.php').read_text(encoding='utf-8')
    reader = (ROOT / 'scripts/market_collector/coverage_read.php').read_text(encoding='utf-8')
    if not selection.startswith('<?php') or not reader.startswith('<?php'):
        raise remote.ProbeError('COVERAGE_SOURCE_INVALID')
    return selection[len('<?php'):].lstrip() + '\n' + reader[len('<?php'):].lstrip()


def execute(env, paramiko=None):
    report = dict(ok=False, stage='configuration', ssh='NOT_CHECKED', host_key='NOT_CHECKED',
                  provider_requests=0, database_writes=0, database_connections=0,
                  secrets_in_log='NEIN/PASS')
    try:
        config = profile.configuration(env)
        isin = env.get('MOSA_MARKET_AUDIT_ISIN', '')
        audit = bool(isin)
        if audit and (not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', isin)
                      or not env.get('MOSA_TEST_DB_PASSWORD')):
            raise remote.ProbeError('ROUTE_AUDIT_CONFIGURATION')
        php_source = source()
        if audit:
            report['gettex_private_use_configured'] = env.get('MOSA_MARKET_GETTEX_PRIVATE_USE') == '1'
            provider = json.loads((ROOT/'config/collector-provider-budget.json').read_text())['providers'].get('gettex_mund_delayed_v1', {})
            report['gettex_documented_limit_configured'] = isinstance(provider.get('documented_provider_limit'), dict)
        if paramiko is None:
            import paramiko
        logging.getLogger('paramiko').disabled = True
        report['stage'] = 'ssh'
        with shared.ssh_client(config, report, paramiko) as transport:
            report['stage'] = 'php_capability'
            report['capability_attempts'] = []
            binary, attempts = remote.capability(transport, report['capability_attempts'])
            report['dogado_php84_cli'] = 'PASS'
            report['stage'] = 'coverage_read'
            args = {'source': php_source}
            if audit:
                args.update(audit_isin=isin, writer_password=env['MOSA_TEST_DB_PASSWORD'])
            payload = json.dumps(args).encode('utf-8')
            code, output, errors, elapsed = remote.remote_call(transport, remote.command(binary, remote.BOOTSTRAP), payload, timeout=90)
            if code or errors:
                raise remote.ProbeError('COVERAGE_REMOTE_PROCESS_FAILED')
            result = json.loads(output)
            if not isinstance(result, dict) or result.get('ok') is not True:
                raise remote.ProbeError('COVERAGE_RESULT_INVALID')
            coverage = result.get('coverage')
            if not isinstance(coverage, dict) or coverage.get('provider_requests') != 0 or coverage.get('database_writes') != 0:
                raise remote.ProbeError('COVERAGE_WRITE_OR_PROVIDER_GUARD')
            report['coverage'] = coverage
            report['remote_elapsed_ms'] = elapsed
            report['database_connections'] = coverage.get('database_connections', 0)
            report['ok'] = coverage.get('database', {}).get('rollback_confirmed') is True
        report['stage'] = 'finished'
    except shared.ConfigurationError as error:
        report['failure'] = str(error)
    except remote.ProbeError as error:
        report['failure'] = str(error)
    except Exception as error:
        report['failure_type'] = type(error).__name__
    return report


def main():
    report = execute(__import__('os').environ)
    text = shared.public_text(report, __import__('os').environ)
    print(text, flush=True)
    summary = __import__('os').environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write('MOSA-2 general market coverage read-only\n\n```json\n' + text + '\n```\n')
    return 0 if report['ok'] and json.loads(text).get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
