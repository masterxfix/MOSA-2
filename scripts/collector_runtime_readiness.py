"""Fileless Dogado runtime assessment. No provider, DB, installation or file transfer."""
import json
import logging
import os
from pathlib import Path
import sys

import collector_actions as shared
import collector_db_locality as remote

ROOT=Path(__file__).resolve().parents[1]


def sources():
    php=(ROOT/'scripts/market_collector/runtime_readiness_probe.php').read_text(encoding='utf-8')
    if not php.startswith('<?php\n'):
        raise remote.ProbeError('PHP_PROBE_SOURCE_INVALID')
    python=(ROOT/'scripts/market_collector/runtime_readiness_probe.py').read_text(encoding='utf-8')
    return php[len('<?php\n'):],python


def execute(env,paramiko=None):
    report=dict(ok=False,stage='configuration',ssh='NOT_CHECKED',host_key='NOT_CHECKED',
                collector_runtime_ready=False,provider_requests=0,database_connections=0,
                business_writes=0,remote_file_operations=0)
    try:
        config=shared.configuration(env)
        php,python=sources()
        if paramiko is None:
            import paramiko
        logging.getLogger('paramiko').disabled=True
        report['stage']='ssh'
        with shared.ssh_client(config,report,paramiko) as transport:
            report['stage']='php_capability'
            report['php_capability_attempts']=[]
            binary,attempts=remote.capability(transport,report['php_capability_attempts'])
            report['stage']='harmless_process_probe'
            # No DB password or other secret is included in the remote payload.
            data=json.dumps(dict(source=php,python_source=python)).encode('utf-8')
            code,output,errors,elapsed=remote.remote_call(transport,remote.command(binary,remote.BOOTSTRAP),data,timeout=75)
            if code or errors:
                raise remote.ProbeError('REMOTE_READINESS_PROCESS_FAILED')
            result=json.loads(output)
            if not isinstance(result,dict):
                raise remote.ProbeError('REMOTE_READINESS_OUTPUT_INVALID')
            report['probe']=result
            report['command_elapsed_ms']=elapsed
            report['collector_runtime_ready']=result.get('ok') is True
            report['ok']=result.get('assessment_complete') is True
        report['stage']='finished'
    except shared.ConfigurationError as error:
        report['failure']=str(error)
    except remote.ProbeError as error:
        report['failure']=str(error)
    except Exception as error:
        report['failure_type']=type(error).__name__
    report['secrets_in_log']='NEIN/PASS'
    return report


def main():
    result=execute(os.environ)
    text=shared.public_text(result,os.environ)
    print(text,flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as stream:
            fence=chr(96)*3
            stream.write('MOSA-2 harmless Dogado runtime readiness\n\n'+fence+'json\n'+text+'\n'+fence+'\n')
    # A completed negative readiness assessment is a valid diagnostic outcome.
    return 0 if result['ok'] and json.loads(text).get('ok') else 1


if __name__=='__main__':
    sys.exit(main())
