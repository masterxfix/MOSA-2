"""Two reviewed SEC issuers, one manual run; existing archive/writer/readback.

Only compact evidence is stored. No retry, model, scheduler or deployment.
"""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals import sec_xbrl as sec
from scripts.fundamentals.analysis import build
from scripts.fundamentals.assessment import prepare

AUTH = 'MOSA2-SEC-REVENUE-20261101:'
WORKFLOW = '.github/workflows/fundamentals-sec-once.yml'
PROFILES = (
    dict(cik='0001045810', isin='US67066G1040', name='NVIDIA', sec_names=['NVIDIA CORP','NVIDIA CORPORATION'], years=(2025,2026),
         execution='fundamentals-sec-nvidia-20261101-02', reference='https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm'),
    dict(cik='0001838359', isin='US76655K1034', name='Rigetti Computing', sec_names=['Rigetti Computing, Inc.'], years=(2024,2025),
         execution='fundamentals-sec-rigetti-20261101-02', reference='https://www.sec.gov/Archives/edgar/data/1838359/000110465926023454/rgti-20251231x10k.htm'),
)
PRESERVE = [dict(isin='DE000A0JBPG2',name='PNE AG',observations=11,current=6),
            dict(isin='DE0005313704',name='Carl Zeiss Meditec',observations=20,current=10),
            dict(isin='AU000000DRO2',name='DroneShield',observations=14,current=7)]
TOTALS = dict(m2_fundamental_observations=59,m2_fundamental_current=30,m2_market_observations=28,m2_market_current=5)
ERRORS = {'SEC_IDENTITY','SEC_NUMBER','SEC_BOUND','SEC_RESPONSE_BINDING','SEC_YEARS','SEC_DUPLICATE_KEY',
    'SEC_REVENUE_REVIEW','SEC_CONFLICTING_REVENUE_TAGS','SEC_TARGET_BASELINE','SEC_STRUCTURE','SEC_PERIOD','SEC_FILING_DATE','SEC_ACCESSION','SEC_FY_ANCHOR_MISSING','SEC_PERIOD_CONFLICT',
    'SEC_PERIOD_CONTINUITY','SEC_CONFLICTING_FILINGS','SEC_NO_QUALIFIED_FACTS','SEC_EVIDENCE_BOUND',
    'SEC_SNAPSHOT_PROCESS','SEC_SNAPSHOT_READBACK','SEC_ASSET_BASELINE','SEC_ASSET_IDENTITY','SEC_WORKFLOW',
    'SEC_CONTACT_MISSING','SEC_CONTACT_BINDING','SEC_TARGET_NOT_EMPTY','SEC_ACCESS_DENIED','SEC_HTTP_STATUS',
    'SEC_CONTENT_TYPE','SEC_ANALYSIS_BINDING'}


def read_snapshot(env, port, totals):
    child={k:env[k] for k in ('PATH','HOME','LANG','SYSTEMROOT','TEMP','TMP') if k in env}
    p=subprocess.run(['php',str(shared.ROOT/'scripts/fundamentals/analysis_read.php')],
        input=json.dumps(dict(password=env['MOSA_TEST_DB_PASSWORD'],port=port,expected_totals=totals)),
        text=True,capture_output=True,timeout=600,env=child,cwd=shared.ROOT)
    if p.stderr or len(p.stdout)>262144:raise ValueError('SEC_SNAPSHOT_PROCESS')
    data=json.loads(p.stdout)
    if p.returncode or data.get('ok') is not True:raise ValueError('SEC_SNAPSHOT_READBACK')
    if len(data['assets'])!=9 or data['excluded_etfs']!=0:raise ValueError('SEC_ASSET_BASELINE')
    return data


def select_asset(data, profile):
    assets=[a for a in data['assets'] if profile['isin'] in [x['normalized_value'] for x in a['identifiers']]]
    if len(assets)!=1 or assets[0]['name']!=profile['name']:raise ValueError('SEC_ASSET_IDENTITY')
    return assets[0]


def guard(env):
    shared.guard(env,dict(authorization=AUTH,reusable_manual=True))
    if env.get('GITHUB_RUN_NUMBER')!='2':raise ValueError('SEC_WORKFLOW')
    if env.get('GITHUB_WORKFLOW_REF')!='masterxfix/MOSA-2/'+WORKFLOW+'@refs/heads/main':raise ValueError('SEC_WORKFLOW')
    # Contact is existing reviewed repository commit metadata, not invented.
    contact=env.get('SEC_CONTACT','')
    if not re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',contact) or contact.endswith('@users.noreply.github.com'):
        raise ValueError('SEC_CONTACT_MISSING')
    author=subprocess.check_output(['git','show','-s','--format=%ae',env['GITHUB_SHA']],cwd=shared.ROOT,text=True).strip()
    if contact!=author:raise ValueError('SEC_CONTACT_BINDING')
    return 'MOSA-2/1.0 masterxfix/MOSA-2 '+contact


def execute(env):
    report=dict(ok=False,provider_requests=0,model_calls=0,full_responses_archived=0,reports=[])
    stage='GUARDS';http=None;pending_write=False
    try:
        agent=guard(env);shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        logging.getLogger('paramiko').disabled=True
        stage='SSH';ssh_start=time.monotonic()
        with shared.access.ssh_client(config,{},paramiko) as transport:
            with shared.access.tunnel(transport,{}) as port:
                report['ssh_setup_ms']=(time.monotonic()-ssh_start)*1000
                stage='BASELINE_SNAPSHOT'
                before=read_snapshot(env,port,TOTALS)
                for profile in PROFILES:
                    asset=select_asset(before,profile)
                    expected=(6,3) if profile['cik']==PROFILES[0]['cik'] else (8,4)
                    if (len(asset['facts']),len(asset['current']))!=expected or any(r['metric_key']=='revenue' for r in asset['facts']):raise ValueError('SEC_TARGET_BASELINE')
                preserved=list(PRESERVE); totals=dict(TOTALS)
                for profile in PROFILES:
                    item=dict(name=profile['name'],ok=False,provider_requests=0);report['reports'].append(item)
                    identity=dict(isin=profile['isin'],name=profile['name'])
                    selected=dict(identity=identity,preserve_assets=preserved,execution=profile['execution'],authorization=AUTH)
                    stage='DB_PREFLIGHT'
                    inspected,elapsed=shared.database(env,port,'inspect',selected=selected)
                    item['preflight_runner_ms']=elapsed
                    stage='PRIVATE_RESERVATION'
                    reserved=shared.archive(transport,'reserve',env,selected=selected)
                    stage='SEC_GET'
                    http=shared.ReadOnlyHttpTransport(shared.HttpGet(None,sec.url(profile['cik']),
                        (('Accept','application/json'),('Accept-Encoding','identity'),('User-Agent',agent))),timeout=60,max_bytes=16*1024*1024)
                    started=time.monotonic()
                    # Count attempted requests before I/O, including unknown outcomes.
                    report['provider_requests']+=1;item['provider_requests']=1
                    response=http.fetch(None);item['provider_ms']=(time.monotonic()-started)*1000
                    item['http_status']=response.http_status
                    if response.http_status!=200:raise ValueError('SEC_ACCESS_DENIED' if response.http_status in (403,429) else 'SEC_HTTP_STATUS')
                    if response.content_type.split(';')[0].strip().lower()!='application/json':raise ValueError('SEC_CONTENT_TYPE')
                    raw=response.payload_bytes
                    meta=dict(url=sec.url(profile['cik']),request_started_at=http.request_started_at,observed_at=response.collected_at,
                        http_status=response.http_status,content_type=response.content_type,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                        execution=profile['execution'],commit=env['GITHUB_SHA'])
                    stage='SEC_QUALIFICATION'
                    mapping={k:profile[k] for k in ('cik','isin','sec_names','reference')};mapping['verification']='reviewed_cik_isin'
                    mapping['revenue_reviews']=json.loads((shared.ROOT/'scripts/fundamentals/sec_revenue_reviews.json').read_text())[profile['cik']]
                    plan=sec.parse(raw,meta,identity,mapping,profile['years'],revenue_only=True)
                    if len(plan['observations'])!=2:raise ValueError('SEC_REVENUE_REVIEW')
                    plan['roundtrip_probe']=True
                    del raw,response;http.last_response=None
                    stage='EVIDENCE_ARCHIVE'
                    compact=plan['evidence_json'].encode('utf-8');stored=plan['stored_evidence']
                    shared.archive(transport,'archive',env,reserved['identity'],stored,compact,selected=selected)
                    plan['archive']=shared.archive(transport,'verify',env,reserved['identity'],stored,selected=selected)
                    item.update(response_sha256=meta['sha256'],evidence_sha256=stored['sha256'],evidence_bytes=len(compact),evidence='PASS',
                        periods={y:dict(start=p['start'],end=p['end']) for y,p in plan['reported_periods'].items()},data_gaps=plan['unqualified_metrics'])
                    stage='DB_APPLY_AND_READBACK';pending_write=True
                    result,elapsed=shared.database(env,port,'apply',selected=selected,baseline=inspected['baseline'],protected=inspected['protected'],asset_id=inspected['asset_id'],plan=plan)
                    stage='FINAL_EVIDENCE_READBACK'
                    shared.archive(transport,'verify',env,reserved['identity'],stored,selected=selected)
                    pending_write=False
                    item.update(result,apply_runner_ms=elapsed)
                    totals['m2_fundamental_observations']+=result['observations'];totals['m2_fundamental_current']+=result['current']
                    preserved=preserved+[dict(**identity,observations=len(select_asset(before,profile)['facts'])+result['observations'],current=len(select_asset(before,profile)['current'])+result['current'])]
                    del plan,compact
                stage='INDEPENDENT_ANALYSIS_READBACK'
                final=read_snapshot(env,port,totals)
                for profile,item in zip(PROFILES,report['reports']):
                    asset=select_asset(final,profile);snapshot=build(asset,final['sources']);prepare(snapshot)
                    if not snapshot['facts'] or not snapshot['current_observation_ids'] or any(f['currency']!='USD' for f in snapshot['facts']):raise ValueError('SEC_ANALYSIS_BINDING')
                    # Independently bind the fresh analysis to the writer's verified result.
                    fields=('metric_key','value_decimal','unit_key','fiscal_year','period_start','period_end','field_path')
                    normalize=lambda rows:sorted(tuple(str(Decimal(str(r[k])).normalize()) if k=='value_decimal' else str(r[k]) for k in fields) for r in rows)
                    if normalize([r for r in asset['facts'] if r['metric_key']=='revenue'])!=normalize(item['verified_facts']):raise ValueError('SEC_ANALYSIS_BINDING')
                    old=select_asset(before,profile)
                    if [r for r in asset['facts'] if r['metric_key']!='revenue']!=old['facts'] or {k:v for k,v in asset['current'].items() if k!='revenue:fy'}!=old['current']:raise ValueError('SEC_TARGET_BASELINE')
                    item['analysis']=dict(contract=snapshot['contract'],reference_check='PASS',currency='USD',
                        calculations=snapshot['calculations'],missing_metrics=snapshot['missing_metrics'],warnings=snapshot['warnings'])
                count=sum(bool(a['facts']) for a in final['assets'])
                report.update(ok=True,stage='SUCCESS',with_fundamentals=count,without_fundamentals=9-count,validated_totals=final['validated_totals'],
                    independent_analysis_readback='PASS',old_assets_unchanged=True,market_unchanged=True,commit=env['GITHUB_SHA'])
    except Exception as error:
        code=str(error)
        report.update(stage=stage,error_code=code if code in ERRORS else 'SAFE_PHASE_FAILURE',
                      outcome='UNKNOWN_NO_RETRY' if pending_write else 'STOP_NO_RETRY')
        if type(error) is RuntimeError and code in {'INPUT','IDENTITY','SCHEMA6','PLAN','TRANSACTION','COMMIT','INDEPENDENT_READBACK'}:report['db_stage']=code
    return report


if __name__=='__main__':
    result=execute(os.environ);print(shared.access.public_text(result,os.environ));sys.exit(0 if result['ok'] else 1)
