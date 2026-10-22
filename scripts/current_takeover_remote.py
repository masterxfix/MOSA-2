"""Manual preparation / explicitly authorized use of the EXISTING Current writer."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from scripts import current_preview_remote as reader
from scripts.market_current import takeover, sealed, preview, process


def php(request):
    child={k:os.environ[k] for k in ('PATH','HOME','LANG','SYSTEMROOT','TEMP','TMP') if k in os.environ}
    child['PYTHONDONTWRITEBYTECODE']='1'
    if request.get('operation')=='apply':
        return process.run(['php',str(ROOT/'scripts/market_current/takeover.php')],request,child,ROOT)
    # Readiness never writes; a separate small budget cannot consume the apply verification reserve.
    result=subprocess.run(['php',str(ROOT/'scripts/market_current/takeover.php')],input=json.dumps(request),
        text=True,capture_output=True,env=child,cwd=ROOT,timeout=60)
    if result.returncode or result.stderr:raise ValueError('private PHP failed')
    reply=json.loads(result.stdout.splitlines()[-1])
    if reply.get('ok') is not True:raise ValueError('private PHP rejected')
    return reply


def writer_call(env,paramiko,operation,**values):
    config=reader.access.configuration(env)
    result=None
    try:
        with reader.access.ssh_client(config,{},paramiko) as transport:
            with reader.access.tunnel(transport,{}) as port:
                runtime=dict(project=str(ROOT),python=sys.executable,runtime_path=env['PATH'],db_port=port)
                result=php(dict(operation=operation,password=env['MOSA_TEST_DB_PASSWORD'],port=port,
                    config=runtime,attempt=env['GITHUB_RUN_ATTEMPT'],**values))
        return result
    except Exception:
        if operation!='apply':raise
        if result is not None:
            return dict(result,status='ERROR_AFTER_COMMIT' if result.get('commit')=='CONFIRMED' else 'OUTCOME_UNKNOWN',
                cause='TRANSPORT_CLEANUP_ERROR')
        return process.outcome('',cause='TRANSPORT_ERROR')


def prepare(env,paramiko):
    def consume(snapshot,report):
        plan=takeover.prepare(snapshot,'current-once-'+env['GITHUB_RUN_ID'],env['GITHUB_SHA'])
        readiness=writer_call(env,paramiko,'readiness')
        envelope=sealed.seal(plan,env['TAKEOVER_RECIPIENT_PUBLIC_KEY'],env['MOSA_TEST_SFTP_PASSWORD'])
        out=Path(env['RUNNER_TEMP'])/'current-takeover-plan.sealed.json'
        out.write_text(json.dumps(envelope),encoding='utf-8');out.chmod(0o600)
        return dict(status='EXACT_PLAN_PENDING_AUTHORIZATION',plan_sha256=takeover.digest(plan),run_id=plan['run_id'],
            writer_readiness=readiness['status'],lock_query_readonly_proof=readiness.get('lock_query_readonly_proof'),**preview.public_summary(report))
    return reader.execute(env,paramiko,consume)


def api(env,path):
    req=urllib.request.Request('https://api.github.com/repos/masterxfix/MOSA-2/'+path,
        headers={'Authorization':'Bearer '+env['GH_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'MOSA-2-current-once'})
    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
            if urlparse(newurl).hostname!='api.github.com':redirected.remove_header('Authorization')
            return redirected
    with urllib.request.build_opener(SafeRedirect()).open(req,timeout=30) as f:return f.read()


def artifact_plan(env):
    source=env['TAKEOVER_PLAN_SOURCE_RUN']
    if not source.isdigit():raise ValueError('source')
    run=json.loads(api(env,'actions/runs/'+source))
    if run['head_sha']!=env['GITHUB_SHA'] or run['conclusion']!='success' or run['run_attempt']!=1:raise ValueError('source revision')
    artifacts=json.loads(api(env,'actions/runs/'+source+'/artifacts'))['artifacts']
    matches=[a for a in artifacts if a['name']=='current-takeover-sealed-plan' and not a['expired']]
    if len(matches)!=1:raise ValueError('artifact')
    raw=api(env,'actions/artifacts/'+str(matches[0]['id'])+'/zip')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.namelist()!=['current-takeover-plan.sealed.json']:raise ValueError('artifact scope')
        envelope=json.loads(z.read(z.namelist()[0]))
    plan=sealed.open_plan(envelope,password=env['MOSA_TEST_SFTP_PASSWORD'])
    if plan['run_id']!='current-once-'+source:raise ValueError('run')
    return plan


def no_previous_claim(env):
    source=env['TAKEOVER_PLAN_SOURCE_RUN']
    if 'current-once-'+source in takeover.CONSUMED_RUN_IDS:raise ValueError('consumed')
    claims=json.loads(api(env,'actions/artifacts?name=current-takeover-consumed-'+source))['artifacts']
    if len(claims)!=1 or str(claims[0]['workflow_run']['id'])!=env['GITHUB_RUN_ID'] or claims[0]['expired']:
        raise ValueError('missing or previous claim')


def apply(env,paramiko):
    try:
        plan=artifact_plan(env)
        if plan['revision']!=env['GITHUB_SHA']:raise ValueError('revision')
        from datetime import datetime,timezone
        now=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')
        takeover.approvals(plan,env['TAKEOVER_AUTHORIZATION'],now)
        no_previous_claim(env)
    except Exception:
        return dict(status='PREFLIGHT_FAILED_NO_WRITE',commit='NOT_ATTEMPTED',write_attempted=False,
            cause='AUTHORIZATION_OR_CLAIM_REJECTED',retry_allowed=False)
    # Explicit authorization has passed; there are no automatic retries anywhere.
    return writer_call(env,paramiko,'apply',takeover=dict(plan=plan,authorization=env['TAKEOVER_AUTHORIZATION']))


if __name__=='__main__':
    dispatched=False
    try:
        import paramiko
        env=os.environ
        if env.get('GITHUB_RUN_ATTEMPT')!='1':raise ValueError('attempt')
        mode=env.get('TAKEOVER_MODE')
        if mode=='PREPARE':result=prepare(env,paramiko)
        elif mode=='APPLY':
            dispatched=True;result=apply(env,paramiko)
        else:raise ValueError('mode')
        print(json.dumps(result,ensure_ascii=False))
        if result.get('status') not in ('EXACT_PLAN_PENDING_AUTHORIZATION','CURRENT_COMMITTED_READBACK_AND_REPLAY_PASS'):sys.exit(1)
    except Exception:
        print(json.dumps(dict(status='OUTCOME_UNKNOWN' if dispatched else 'PREFLIGHT_FAILED_NO_WRITE',
            cause='OUTER_PROCESS_ERROR',retry_allowed=False,reconciliation='SEPARATE_READ_ONLY_EXISTING_RECONCILE')))
        sys.exit(1)
