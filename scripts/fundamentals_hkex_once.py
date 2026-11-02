"""One authorized HKEX import: two direct PDF GETs, compact Evidence, shared writer."""
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time
from urllib import error, parse, request

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals_sec_once import read_snapshot
from scripts.fundamentals import hkex
from scripts.fundamentals.analysis import build
from scripts.fundamentals.assessment import prepare

AUTH = os.environ.get('HKEX_AUTH_PREFIX', 'MOSA2-HKEX-FUNDAMENTALS-SECOND-20261102:')
WORKFLOW = os.environ.get('HKEX_WORKFLOW', '.github/workflows/fundamentals-hkex-once.yml')
TOTALS = dict(m2_fundamental_observations=79, m2_fundamental_current=40,
              m2_market_observations=28, m2_market_current=5)
EXECUTIONS = {
    'CNE100000296': 'fundamentals-hkex-byd-20261102-01',
    'CNE100006CQ4': 'fundamentals-hkex-ubtech-20261102-01',
}
PRESERVE = (
    dict(isin='DE000A0JBPG2', name='PNE AG', observations=11, current=6),
    dict(isin='DE0005313704', name='Carl Zeiss Meditec', observations=20, current=10),
    dict(isin='AU000000DRO2', name='DroneShield', observations=14, current=7),
    dict(isin='US67066G1040', name='NVIDIA', observations=8, current=4),
    dict(isin='US76655K1034', name='Rigetti Computing', observations=10, current=5),
    dict(isin='NO0010081235', name='NEL ASA', observations=6, current=3),
    dict(isin='DK0060252690', name='Pandora', observations=10, current=5),
)
PROFILES = tuple(dict(profile=p, execution=EXECUTIONS[p['isin']]) for p in hkex.PROFILES)
EXPECTED = json.loads((shared.ROOT / 'scripts/fundamentals/hkex_expected.json').read_text(encoding='utf-8'))
SAFE = {
    'HKEX_WORKFLOW', 'HKEX_SOURCE_HASH_MISMATCH', 'HKEX_VALUE_MISMATCH', 'HKEX_TARGET_BASELINE',
    'HKEX_SOURCE_URL', 'HKEX_HTTP_STATUS', 'HKEX_CONTENT_TYPE', 'HKEX_PDF_BOUND', 'HKEX_PROVIDER_GET',
    'HKEX_RESPONSE', 'HKEX_IDENTITY', 'HKEX_STANDARD', 'HKEX_CONSOLIDATION', 'HKEX_UNIT',
    'HKEX_REPORT_YEAR', 'HKEX_REPORT_END', 'HKEX_YEAR_COLUMNS', 'HKEX_REVENUE_AMBIGUOUS',
    'HKEX_OPERATING_PROFIT_AMBIGUOUS', 'HKEX_PROFIT_BEFORE_TAX_AMBIGUOUS',
    'HKEX_PROFIT_AFTER_TAX_AMBIGUOUS', 'HKEX_OPERATING_CASHFLOW_AMBIGUOUS', 'HKEX_EVIDENCE_BOUND',
    'HKEX_RESPONSE_BINDING', 'HKEX_RESPONSE_MIME', 'HKEX_RESPONSE_HASH', 'HKEX_PROFILE',
    'HKEX_SNAPSHOT', 'HKEX_ANALYSIS', 'HKEX_PRESERVATION', 'HKEX_FINAL_TOTALS', 'ARCHIVE_PROCESS',
    'ARCHIVE_RESULT', 'OTHER_ACTIONS_ACTIVE', 'STOP_NO_RETRY',
}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')


def guard(env):
    shared.guard(env, dict(authorization=AUTH, reusable_manual=True))
    need(env.get('GITHUB_RUN_NUMBER') == '2', 'HKEX_WORKFLOW')
    need(env.get('GITHUB_WORKFLOW_REF') == 'masterxfix/MOSA-2/' + WORKFLOW + '@refs/heads/main', 'HKEX_WORKFLOW')


def asset_fingerprint(asset):
    encoded=json.dumps(asset,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def assets_with_fundamentals(snapshot):
    result=[]
    for expected in PRESERVE:
        matches=[a for a in snapshot['assets'] if expected['isin'] in [i['normalized_value'] for i in a['identifiers']]]
        need(len(matches)==1 and matches[0]['name']==expected['name'], 'HKEX_PRESERVATION')
        asset=matches[0]
        need(len(asset['facts'])==expected['observations'] and len(asset['current'])==expected['current'], 'HKEX_PRESERVATION')
        result.append(dict(expected,fingerprint=asset_fingerprint(asset)))
    need(len(result)==7 and {a['isin'] for a in result}=={p['isin'] for p in PRESERVE}, 'HKEX_PRESERVATION')
    return result


def select_asset(snapshot, profile):
    matches=[a for a in snapshot['assets'] if profile['isin'] in [i['normalized_value'] for i in a['identifiers']]]
    need(len(matches)==1 and matches[0]['name'] in profile['names'], 'HKEX_IDENTITY')
    return matches[0]


def execution_overrides(raw=None):
    raw=os.environ.get('HKEX_EXECUTION_OVERRIDES', '') if raw is None else raw
    if not raw:
        return {}
    try:
        values=json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise ValueError('HKEX_WORKFLOW') from None
    expected=set(EXECUTIONS)
    need(isinstance(values,dict) and set(values)==expected and values==EXECUTIONS, 'HKEX_WORKFLOW')
    return values


def execution_for(profile):
    overrides=execution_overrides()
    need(profile['isin'] in EXECUTIONS, 'HKEX_WORKFLOW')
    execution=overrides.get(profile['isin'], EXECUTIONS[profile['isin']])
    need(execution==EXECUTIONS[profile['isin']], 'HKEX_WORKFLOW')
    return execution


def download(profile, item):
    """One direct PDF GET, no redirects and no retry."""
    class NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    url=profile['url'];parts=parse.urlparse(url)
    need(parts.scheme=='https' and parts.hostname=='www1.hkexnews.hk' and not parts.username and not parts.password and not parts.fragment, 'HKEX_SOURCE_URL')
    opener=request.build_opener(request.ProxyHandler({}), NoRedirect())
    started=stamp();item['provider_requests']=1
    req=request.Request(url,headers={'Accept':'application/pdf','Accept-Encoding':'identity','User-Agent':'MOSA-2 HKEX qualified fundamentals'})
    try:
        response=opener.open(req,timeout=90)
    except error.HTTPError as exc:
        raise ValueError('HKEX_HTTP_STATUS') from exc
    except Exception as exc:
        raise ValueError('HKEX_PROVIDER_GET') from exc
    with response:
        need(response.status==200, 'HKEX_HTTP_STATUS')
        mime=response.headers.get('Content-Type','').split(';',1)[0].strip().lower()
        need(mime=='application/pdf', 'HKEX_CONTENT_TYPE')
        raw=response.read(hkex.MAX_BYTES+1)
    need(0<len(raw)<=hkex.MAX_BYTES, 'HKEX_PDF_BOUND')
    meta=dict(url=url,request_started_at=started,observed_at=stamp(),http_status=200,
              content_type=mime,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    expected=EXPECTED['profiles'][profile['profile_key']]
    need(meta['sha256']==expected['response_sha256'], 'HKEX_SOURCE_HASH_MISMATCH')
    return raw,meta


def compare_plan(plan, profile):
    expected=EXPECTED['profiles'][profile['profile_key']]
    need(len(plan['observations'])==10 and len(plan['metrics'])==5, 'HKEX_VALUE_MISMATCH')
    need(plan['identity']['isin']==expected['isin'], 'HKEX_VALUE_MISMATCH')
    need(plan['units'][0]['unit_key']==EXPECTED['unit_key'] and plan['units'][0]['monetary_currency_code']==EXPECTED['currency'], 'HKEX_VALUE_MISMATCH')
    need(plan['units'][0]['scale_numerator']==EXPECTED['scale_numerator'] and plan['units'][0]['scale_denominator']==EXPECTED['scale_denominator'], 'HKEX_VALUE_MISMATCH')
    actual={(r['metric_key'],r['fiscal_year']):r['value_decimal'] for r in plan['observations']}
    wanted={(metric,year):value for metric,periods in expected['values'].items() for year,value in periods.items()}
    need(actual==wanted, 'HKEX_VALUE_MISMATCH')


def execute(env):
    report=dict(ok=False,provider_requests=0,http_requests=0,model_calls=0,full_responses_archived=0,reports=[])
    stage='GUARDS';pending_write=False
    try:
        guard(env);execution_overrides();shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        logging.getLogger('paramiko').disabled=True
        with shared.access.ssh_client(config,{},paramiko) as transport:
            with shared.access.tunnel(transport,{}) as port:
                stage='BASELINE_SNAPSHOT';before=read_snapshot(env,port,TOTALS)
                preserved=assets_with_fundamentals(before)
                need(len(preserved)==7, 'HKEX_PRESERVATION')
                selected=[]
                for entry in PROFILES:
                    asset=select_asset(before,entry['profile'])
                    need(not asset['facts'] and not asset['current'], 'HKEX_TARGET_BASELINE')
                    selected.append(dict(entry,identity=dict(isin=entry['profile']['isin'],name=asset['name']),
                                         execution=execution_for(entry['profile']),authorization=AUTH,
                                         preserve_assets=list(preserved)))
                packages=[]
                for item in selected:
                    profile=item['profile'];entry=dict(isin=profile['isin'],ok=False,provider_requests=0);report['reports'].append(entry)
                    stage='DB_PREFLIGHT';inspected,elapsed=shared.database(env,port,'inspect',selected=item);entry['preflight_runner_ms']=elapsed
                    stage='PRIVATE_RESERVATION';reserved=shared.archive(transport,'reserve',env,selected=item)
                    stage='HKEX_GET';started=time.monotonic();raw,meta=download(profile,entry);entry['provider_ms']=(time.monotonic()-started)*1000
                    meta.update(execution=item['execution'],commit=env['GITHUB_SHA'])
                    stage='HKEX_QUALIFICATION';plan=hkex.parse(raw,meta,profile,item['identity']);compare_plan(plan,profile);del raw
                    stage='EVIDENCE_ARCHIVE';compact=plan['evidence_json'].encode('utf-8');stored=plan['stored_evidence']
                    shared.archive(transport,'archive',env,reserved['identity'],stored,compact,selected=item)
                    plan['archive']=shared.archive(transport,'verify',env,reserved['identity'],stored,selected=item)
                    entry.update(response_sha256=meta['sha256'],response_bytes=meta['bytes'],evidence_sha256=stored['sha256'],
                                 evidence_bytes=len(compact),evidence='PASS',periods=plan['reported_periods'],
                                 currency=plan['units'][0]['monetary_currency_code'],data_gaps=plan['unqualified_metrics'])
                    packages.append(dict(item=item,plan=plan,stored=stored,reserved=reserved,preflight=inspected,compact=compact))
                totals=dict(TOTALS);preserve_by_isin={a['isin']:a for a in preserved}
                for package in packages:
                    item=package['item'];stage='DB_APPLY_AND_READBACK';
                    inspected,elapsed=shared.database(env,port,'inspect',selected=item);item['preflight_after_previous_ms']=elapsed
                    pending_write=True
                    result,elapsed=shared.database(env,port,'apply',selected=item,baseline=inspected['baseline'],protected=inspected['protected'],
                                                   asset_id=inspected['asset_id'],plan=package['plan'])
                    stage='FINAL_EVIDENCE_READBACK';shared.archive(transport,'verify',env,package['reserved']['identity'],package['stored'],selected=item)
                    pending_write=False;item.update(result,apply_runner_ms=elapsed,ok=True)
                    totals['m2_fundamental_observations']+=result['observations'];totals['m2_fundamental_current']+=result['current']
                    del package['plan'],package['compact']
                stage='INDEPENDENT_ANALYSIS_READBACK';final=read_snapshot(env,port,totals)
                for old in before['assets']:
                    isin=old['identifiers'][0]['normalized_value'];new=select_asset(final,next(e['profile'] for e in PROFILES if e['profile']['isin']==isin)) if isin in EXECUTIONS else next(a for a in final['assets'] if isin in [i['normalized_value'] for i in a['identifiers']])
                    if isin in preserve_by_isin: need(asset_fingerprint(new)==preserve_by_isin[isin]['fingerprint'], 'HKEX_PRESERVATION')
                    elif isin not in EXECUTIONS: need(new==old, 'HKEX_PRESERVATION')
                    else: need({k:v for k,v in new.items() if k not in ('facts','current')}=={k:v for k,v in old.items() if k not in ('facts','current')}, 'HKEX_PRESERVATION')
                for entry,item in zip(PROFILES,report['reports']):
                    asset=select_asset(final,entry['profile']);snapshot=build(asset,final['sources']);prepare(snapshot)
                    need(len(snapshot['facts'])==10 and len(snapshot['current_observation_ids'])==5, 'HKEX_ANALYSIS')
                    need(all(f['currency']=='CNY' and f['unit']=='CNY_THOUSAND' for f in snapshot['facts']), 'HKEX_ANALYSIS')
                    fields=('metric_key','value_decimal','unit_key','fiscal_year','period_start','period_end','field_path')
                    norm=lambda rows:sorted(tuple(str(r[k]) for k in fields) for r in rows)
                    need(norm(asset['facts'])==norm(item['verified_facts']), 'HKEX_ANALYSIS')
                    item['analysis']=dict(contract=snapshot['contract'],reference_check='PASS',calculations=snapshot['calculations'],
                                          missing_metrics=snapshot['missing_metrics'],warnings=snapshot['warnings'])
                need(final['validated_totals']==totals, 'HKEX_FINAL_TOTALS')
                report.update(ok=True,stage='SUCCESS',with_fundamentals=sum(bool(a['facts']) for a in final['assets']),
                              without_fundamentals=sum(not a['facts'] for a in final['assets']),validated_totals=final['validated_totals'],
                              independent_analysis_readback='PASS',old_assets_unchanged=True,market_unchanged=True,commit=env['GITHUB_SHA'])
    except Exception as exc:
        code=str(exc);report.update(stage=stage,error_code=code if code in SAFE else 'SAFE_PHASE_FAILURE',
                                    outcome='UNKNOWN_NO_RETRY' if pending_write else 'STOP_NO_RETRY')
    report['provider_requests']=sum(item.get('provider_requests',0) for item in report['reports'])
    report['http_requests']=report['provider_requests']
    return report


if __name__=='__main__':
    result=execute(os.environ);print(shared.access.public_text(result,os.environ));
    raise SystemExit(0 if result['ok'] else 1)
