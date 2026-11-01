"""One authorized archive-only application using the existing generic DB writer."""
import hashlib
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scripts import fundamentals_pilot_once as pilot
from scripts.fundamentals import archived_zeiss as archive
from scripts.fundamentals_archive_diagnose import guard, ERRORS

AUTHORIZATION='MOSA2-ZEISS-QUALIFIED-IMPORT-20261101:'

def source():
    definitions=archive.source().split("\nif __name__=='__main__':")[0]
    return definitions+'\n'+(pilot.ROOT/'scripts/fundamentals/archive_import_remote.py').read_text(encoding='utf-8')

def remote_operation(transport,env,action,plan_sha256=None):
    request=dict(execution=archive.EXECUTION,commit=archive.COMMIT,sha256=archive.SHA256,url=archive.zeiss.URL,
        apply_commit=env['GITHUB_SHA'],authorization=env['AUTHORIZATION'],action=action,plan_sha256=plan_sha256)
    bootstrap="import json,sys; p=json.loads(sys.stdin.read()); REQUEST=p['request']; exec(compile(p['source'],'<archive-import>','exec'))"
    code,out,err,_=archive.remote.remote_call(transport,shlex.join([archive.directories.PYTHON,'-I','-B','-c',bootstrap]),
        json.dumps(dict(request=request,source=source())).encode(),timeout=60)
    if err:raise ValueError('REMOTE_STDERR')
    if len(out)>49152:raise ValueError('PLAN_BOUND')
    reply=json.loads(out)
    if not isinstance(reply,dict) or 'ok' not in reply or (code!=0 and reply['ok']):raise ValueError('REMOTE_RESULT_INVALID')
    return reply

def validate_plan(plan):
    m=plan['metadata']
    if (m['sha256']!=archive.SHA256 or m['commit']!=archive.COMMIT or m['execution']!=archive.EXECUTION or
        m['url']!=archive.zeiss.URL or plan['archive']['sha256']!=archive.SHA256 or
        plan['archive']['bytes']!=m['bytes'] or plan['archive']['durable'] is not True):raise ValueError('PLAN_PROVENANCE')
    # Same validation as the unchanged DB transaction, with no connection or secret.
    code="require 'scripts/fundamentals/core.php';try{Mosa2\\Fundamentals\\validate(json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR));echo 'PASS';}catch(Throwable){exit(1);}"
    child={k:os.environ[k] for k in ('PATH','HOME','LANG','SYSTEMROOT','TEMP','TMP') if k in os.environ}
    p=subprocess.run(['php','-r',code],input=json.dumps(plan),text=True,capture_output=True,cwd=pilot.ROOT,env=child,timeout=30)
    if p.returncode or p.stderr or p.stdout!='PASS':raise ValueError('PLAN_VALIDATION')

def execute(env):
    report=dict(ok=False,provider_requests=0,observations=0,current=0,metrics=0)
    stage='GUARDS';started=False
    try:
        guard(env,AUTHORIZATION);pilot.no_other_runs(env)
        config=pilot.access.configuration(env)
        import paramiko
        logging.getLogger('paramiko').disabled=True
        stage='SSH_CONNECT'
        with pilot.access.ssh_client(config,{},paramiko) as transport:
            stage='ARCHIVE_AND_ADAPTER'
            reply=remote_operation(transport,env,'plan')
            if not reply['ok']:
                return report|{k:reply[k] for k in ('phase','error','archive')}
            report['archive']='PASS'
            stage='PLAN_VALIDATION';plan=reply['plan'];validate_plan(plan)
            digest=hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
            if digest!=reply['plan_sha256']:raise ValueError('PLAN_CHANGED')
            report['qualified_metrics']=len(plan['metrics']);report['nested_tables_supported']=True
            report['unqualified_metrics']=plan['unqualified_metrics']
            with pilot.access.tunnel(transport,{}) as port:
                stage='DB_PREFLIGHT'
                db_env=dict(env,FUNDAMENTALS_PROFILE='zeiss')
                before,elapsed=pilot.database(db_env,port,'inspect');report['preflight_runner_ms']=elapsed
                stage='ARCHIVE_RECHECK_AND_MARKER'
                reserved=remote_operation(transport,env,'reserve',digest)
                if not reserved['ok']:return report|{k:reserved[k] for k in ('phase','error','archive')}
                stage='DB_APPLY_AND_READBACK';started=True
                result,elapsed=pilot.database(db_env,port,'apply',baseline=before['baseline'],protected=before['protected'],asset_id=before['asset_id'],plan=plan)
                report.update(result,apply_runner_ms=elapsed)
                stage='FINAL_ARCHIVE_READBACK'
                verified=remote_operation(transport,env,'verify')
                if not verified['ok']:return report|dict(ok=False,phase=stage,error=verified['error'],archive='FAIL')
                report.update(ok=True,archive='PASS',phase='SUCCESS',commit=env['GITHUB_SHA'])
    except Exception as exc:
        allowed=ERRORS|archive.SAFE_REMOTE_CODES|{'RUN_GUARD','PLAN_BOUND','PLAN_CHANGED','PLAN_PROVENANCE','PLAN_VALIDATION',
            'REMOTE_STDERR','REMOTE_RESULT_INVALID','SSH_OUTPUT_LIMIT','SSH_STDERR_LIMIT','SSH_COMMAND_TIMEOUT',
            'SSH_SESSION_CHANNEL_REJECTED','SSH_EXEC_REQUEST_REJECTED','INPUT','IDENTITY','SCHEMA6','PLAN','TRANSACTION','COMMIT','INDEPENDENT_READBACK'}
        report.update(ok=False,phase=stage,error=str(exc) if str(exc) in allowed else 'IMPORT_PHASE_FAILED',
            outcome='UNKNOWN_NO_RETRY' if started else 'NOT_COMMITTED_NO_RETRY')
    return report

if __name__=='__main__':
    result=execute(os.environ);public=pilot.access.public_text(result,os.environ);print(public)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as out:out.write('Archive-only Zeiss import\n\n```json\n'+public+'\n```\n')
    sys.exit(0 if result['ok'] else 1)
