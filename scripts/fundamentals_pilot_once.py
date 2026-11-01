"""One authorized issuer pilot, existing transport/tunnel/private archive; no retries."""
import base64
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
import collector_actions as access
import collector_db_locality as remote
import collector_private_directories as directories
from scripts.schema6_apply_once import no_other_runs
from scripts.market_collector.http_transport import HttpGet,ReadOnlyHttpTransport
from scripts.fundamentals import pne, zeiss
from scripts.fundamentals.html_evidence import evidence

EXECUTION='fundamentals-pne2025-20261101-01'
AUTHORIZATION='MOSA2-PNE-FUNDAMENTALS-ONCE-20261101:'
PROFILES={
    'pne':dict(adapter=pne,execution=EXECUTION,authorization=AUTHORIZATION,
        identity=dict(isin=pne.ISIN,name='PNE AG'),preserve_assets=[]),
    'zeiss':dict(adapter=zeiss,execution='fundamentals-zeiss2025-20261101-01',
        authorization='MOSA2-ZEISS-FUNDAMENTALS-ONCE-20261101:',
        identity=dict(isin=zeiss.ISIN,name='Carl Zeiss Meditec'),
        preserve_assets=[dict(isin=pne.ISIN,name='PNE AG',observations=7,current=4)]),
}

def profile(env):
    return PROFILES[env.get('FUNDAMENTALS_PROFILE','pne')]


def guard(env,selected=None):
    selected=selected or profile(env)
    required=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',
        GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='1')
    if selected.get('reusable_manual'):required.pop('GITHUB_RUN_NUMBER')
    if any(env.get(k)!=v for k,v in required.items()):raise ValueError('RUN_GUARD')
    sha=env.get('GITHUB_SHA','')
    if not re.fullmatch('[0-9a-f]{40}',sha) or env.get('EXPECTED_COMMIT')!=sha or env.get('AUTHORIZATION')!=selected['authorization']+sha:
        raise ValueError('COMMIT_AUTHORIZATION')

def archive(transport,action,env,identity=None,metadata=None,payload=None,selected=None):
    selected=selected or profile(env)
    # Load only definitions from the existing qualified no-follow directory library.
    library=directories.REMOTE_SOURCE.split('\nif __name__=="__main__":')[0]
    source=library+'\n'+(ROOT/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8')
    data=dict(action=action,execution=selected['execution'],commit=env['GITHUB_SHA'],identity=identity,metadata=metadata)
    if payload is not None:data['payload']=base64.b64encode(payload).decode('ascii')
    code,out,err,_=remote.remote_call(transport,shlex.join([directories.PYTHON,'-I','-B','-c',source]),json.dumps(data).encode(),timeout=60)
    if code or err:raise ValueError('ARCHIVE_PROCESS')
    reply=json.loads(out)
    if reply.get('ok') is not True:raise ValueError('ARCHIVE_RESULT')
    return reply['result']

def database(env,port,action,selected=None,**extra):
    selected=selected or profile(env)
    request=dict(action=action,password=env['MOSA_TEST_DB_PASSWORD'],port=port,identity=selected['identity'],preserve_assets=selected['preserve_assets'],
        expected_baseline_counts={'m2_market_current':5,'m2_market_observations':28},**extra)
    child={k:env[k] for k in ('PATH','HOME','LANG','SYSTEMROOT','TEMP','TMP') if k in env}
    start=time.monotonic()
    result=subprocess.run(['php',str(ROOT/'scripts/fundamentals/core.php')],input=json.dumps(request),text=True,
        capture_output=True,cwd=ROOT,env=child,timeout=360)
    if result.stderr or len(result.stdout)>65536:raise ValueError('DB_PROCESS')
    reply=json.loads(result.stdout)
    if result.returncode or reply.get('ok') is not True:
        # Never log driver errors, private plans, IDs or values.
        allowed={'INPUT','IDENTITY','SCHEMA6','PLAN','TRANSACTION','COMMIT','INDEPENDENT_READBACK'}
        raise RuntimeError(reply['stage'] if reply.get('stage') in allowed else 'DB_RESULT')
    return reply,(time.monotonic()-start)*1000

def execute(env,selected=None):
    selected=selected or profile(env);adapter=selected['adapter']
    report=dict(ok=False,execution=selected['execution'],provider_requests=0,original_responses=0,metrics=0,observations=0,current=0)
    stage='GUARDS';http=None
    try:
        guard(env,selected);no_other_runs(env)
        config=access.configuration(env)
        import paramiko
        logging.getLogger('paramiko').disabled=True
        stage='SSH'
        with access.ssh_client(config,{},paramiko) as transport:
            with access.tunnel(transport,{}) as port:
                stage='DB_PREFLIGHT'
                before,elapsed=database(env,port,'inspect',selected=selected)
                report['preflight_runner_ms']=elapsed
                stage='PRIVATE_RESERVATION'
                reserved=archive(transport,'reserve',env,selected=selected)
                stage='PROVIDER_GET'
                http=ReadOnlyHttpTransport(HttpGet(None,adapter.URL,(('Accept',getattr(adapter,'CONTENT_TYPE','text/html')),('Accept-Encoding','identity'))),timeout=30)
                response=http.fetch(None)
                if selected.get('retention')=='derived_evidence':
                    report.update(html_source_reachable=response.http_status==200 and response.content_type.split(';',1)[0].strip().lower()=='text/html',
                        pdf_downloads=0,full_responses_archived=0)
                report['provider_requests']=http.attempt_count
                raw=response.payload_bytes
                if not 0<len(raw)<=8*1024*1024:raise ValueError('PAYLOAD_BOUND')
                metadata=dict(url=adapter.URL,request_started_at=http.request_started_at,observed_at=response.collected_at,
                    http_status=response.http_status,content_type=response.content_type,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                    execution=selected['execution'],commit=env['GITHUB_SHA'])
                derived=selected.get('retention')=='derived_evidence'
                if not derived:
                    stage='RAW_ARCHIVE'
                    archive(transport,'archive',env,reserved['identity'],metadata,raw,selected=selected)
                    verified=archive(transport,'verify',env,reserved['identity'],metadata,selected=selected)
                    report.update(original_responses=1,raw_sha256=metadata['sha256'],raw_bytes=metadata['bytes'],raw_archive='DURABLE_PRIVATE_SHA256_PASS')
                stage='ADAPTER'
                if response.http_status!=200 or response.content_type.split(';',1)[0].strip().lower()!=getattr(adapter,'CONTENT_TYPE','text/html'):
                    raise ValueError('HTTP_RESPONSE')
                plan=adapter.parse(raw,response.collected_at)
                stored_metadata=metadata
                if derived:
                    stage='EVIDENCE_ARCHIVE'
                    compact,stored_metadata=evidence(plan,metadata,selected['identity'])
                    # The full response never leaves runner memory or reaches remote storage.
                    del raw,response
                    http.last_response=None
                    archive(transport,'archive',env,reserved['identity'],stored_metadata,compact,selected=selected)
                    verified=archive(transport,'verify',env,reserved['identity'],stored_metadata,selected=selected)
                    plan['stored_evidence']=stored_metadata
                    report.update(evidence_archive='PASS',full_responses_archived=0,source_classification='independent_third_party')
                plan.update(metadata=metadata,archive=verified)
                if selected.get('periods'):
                    actual={(r['period_type'],r['period_start'],r['period_end']) for r in plan['observations']}
                    if not actual or not actual.issubset(set(selected['periods'])):raise ValueError('REPORT_PERIOD')
                report['unqualified_metrics']=plan.get('unqualified_metrics',[])
                report['qualified_metrics']=len(plan['metrics'])
                report['unit_keys']=[u['unit_key'] for u in plan['units']]
                report['document_evidence']=plan.get('document_evidence',[])
                stage='DB_APPLY_AND_READBACK'
                result,elapsed=database(env,port,'apply',selected=selected,baseline=before['baseline'],protected=before['protected'],asset_id=before['asset_id'],plan=plan)
                stage='FINAL_ARCHIVE_READBACK'
                archive(transport,'verify',env,reserved['identity'],stored_metadata,selected=selected)
                report.update(result,apply_runner_ms=elapsed,publication_date=plan['publication_date'],
                    commit=env['GITHUB_SHA'],provider_requests=http.attempt_count,original_responses=0 if derived else 1,
                    reported_at_policy='NULL_WHEN_NO_EXACT_PUBLICATION_TIMESTAMP',
                    parser_status='qualified_evidence_only' if derived else 'partial_nonqualified_content_preserved_raw')
        report['stage']='SUCCESS'
    except Exception as error:
        if str(error) in {'HTML_REPORT_IDENTITY','HTML_CURRENCY_CONFLICT','HTML_COLUMN_STRUCTURE','HTML_TABLE_BOUND','EVIDENCE_BINDING','EVIDENCE_BOUND','QUARTER_IDENTITY','REPORT_PERIOD','RESULTS_SECTION','UNIT_CONFLICT','FACT_CONFLICT','NO_QUALIFIED_FACTS','PERIOD_CONFLICT','PDF_SIGNATURE_OR_BOUND','PDF_DOCUMENT_BOUND','PDF_EXTRACTION','PDF_YEAR_COLUMNS','PDF_HIGHLIGHTS_TABLE','PDF_DOCUMENT_IDENTITY','PDF_CURRENCY_CONFLICT','PDF_UNIT_CONFLICT','HTTP_RESPONSE','PAYLOAD_BOUND'}:
            report['error_code']=str(error)
        report['stage']=stage
        report['provider_requests']=http.attempt_count if http is not None else 0
        if type(error) is RuntimeError and str(error) in {'INPUT','IDENTITY','SCHEMA6','PLAN','TRANSACTION','COMMIT','INDEPENDENT_READBACK'}:
            report['db_stage']=str(error)
        report['outcome']='UNKNOWN_NO_RETRY' if stage in ('DB_APPLY_AND_READBACK','FINAL_ARCHIVE_READBACK') else 'STOP_NO_RETRY'
    return report

if __name__=='__main__':
    result=execute(os.environ)
    public=access.public_text(result,os.environ)
    print(public)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as out:
            out.write('One-time qualified fundamentals pilot\n\n```json\n'+public+'\n```\n')
    sys.exit(0 if json.loads(public).get('ok') else 1)
