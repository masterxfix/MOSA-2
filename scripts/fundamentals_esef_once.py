"""Authorized ESEF pilot. One acquisition per issuer, no retries or models."""
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from urllib import request, error, parse
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals_sec_once import read_snapshot
from scripts.fundamentals import esef
from scripts.fundamentals.analysis import build
from scripts.fundamentals.assessment import prepare

AUTH = os.environ.get('ESEF_AUTH_PREFIX', 'MOSA2-ESEF-20261101:')
WORKFLOW = os.environ.get('ESEF_WORKFLOW', '.github/workflows/fundamentals-esef-once.yml')
PROFILES = json.loads((shared.ROOT/'scripts/fundamentals/esef_profiles.json').read_text(encoding='utf-8'))


def execution_overrides(raw=None):
    raw = os.environ.get('ESEF_EXECUTION_OVERRIDES', '') if raw is None else raw
    if not raw:
        return {}
    try:
        values = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise ValueError('ESEF_EXECUTION_BINDING') from None
    expected = {'NO0010081235', 'DK0060252690'}
    if not isinstance(values, dict) or set(values) != expected or any(not isinstance(v, str) or not re.fullmatch(
            r'fundamentals-esef-(?:nel|pandora)-20261101-02', v) for v in values.values()):
        raise ValueError('ESEF_EXECUTION_BINDING')
    return values


for _profile in PROFILES:
    _override = execution_overrides().get(_profile['isin'])
    if _override:
        _profile['execution'] = _override

TOTALS = dict(m2_fundamental_observations=63,m2_fundamental_current=32,m2_market_observations=28,m2_market_current=5)
PRESERVE = [('DE000A0JBPG2',11,6),('DE0005313704',20,10),('AU000000DRO2',14,7),('US67066G1040',8,4),('US76655K1034',10,5)]
SAFE = {'ZIP_BOUND','ZIP_PATH','ZIP_TYPE','ZIP_SIZE','XML_DTD','REPORT_COUNT','ZIP_INVALID','LIBRARY_VERSION',
        'ARELLE_LOAD','FACT_BOUND','ARELLE_STRUCTURE','NUMBER','IDENTITY','LEI','ENTITY_NAME','CONSOLIDATED_SCOPE',
        'REPORT_END','YEARS','ANNUAL_PERIOD_AMBIGUOUS','PERIOD_CONTINUITY','NO_QUALIFIED_FACTS','EVIDENCE_BOUND',
        'RESPONSE_BINDING','DOWNLOAD_URL','REDIRECT_LIMIT','HTTP_STATUS','CONTENT_TYPE','TARGET_BASELINE',
        'SNAPSHOT_BINDING','PRESERVATION','WORKFLOW'}


def safe_code(exc):
    code = str(exc)
    return code if code.startswith('ESEF_') and code[5:] in SAFE else 'SAFE_PHASE_FAILURE'


def stamp(): return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')


def guard(env):
    shared.guard(env, dict(authorization=AUTH))
    esef.need(env.get('GITHUB_WORKFLOW_REF')=='masterxfix/MOSA-2/'+WORKFLOW+'@refs/heads/main', 'WORKFLOW')


def asset(snapshot, isin):
    matches=[a for a in snapshot['assets'] if isin in [i['normalized_value'] for i in a['identifiers']]]
    esef.need(len(matches)==1, 'IDENTITY')
    return matches[0]


def download(profile, item):
    """One logical package acquisition, <=2 audited HTTPS redirects, no retry."""
    class NoRedirect(request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    opener=request.build_opener(request.ProxyHandler({}),NoRedirect())
    url=profile['url']; seen=set(); chain=[]; started=stamp()
    item['provider_requests']=1;item['http_requests']=0
    for hop in range(3):
        u=parse.urlsplit(url)
        esef.need(u.scheme=='https' and not u.username and not u.password and u.port in (None,443)
            and not u.fragment and u.hostname and any(u.hostname==d or u.hostname.endswith('.'+d) for d in profile['download_domains'])
            and url not in seen, 'DOWNLOAD_URL')
        seen.add(url);item['http_requests']+=1
        req=request.Request(url,headers={'Accept':'application/zip,application/octet-stream','Accept-Encoding':'identity','User-Agent':'MOSA-2 ESEF qualified fundamentals'})
        try: response=opener.open(req,timeout=90)
        except error.HTTPError as e: response=e
        with response:
            status=response.code; chain.append(dict(url=url,status=status));item['download_chain']=chain
            if status in (301,302,303,307,308):
                esef.need(hop<2 and response.headers.get('Location'), 'REDIRECT_LIMIT')
                url=parse.urljoin(url,response.headers['Location']);continue
            esef.need(status==200,'HTTP_STATUS')
            mime=response.headers.get('Content-Type','').split(';')[0].strip().lower()
            esef.need(mime in ('application/zip','application/x-zip-compressed','application/octet-stream','binary/octet-stream'),'CONTENT_TYPE')
            body=response.read(esef.MAX_ZIP+1);esef.need(0<len(body)<=esef.MAX_ZIP,'ZIP_BOUND')
            return body,dict(url=profile['url'],final_url=url,redirect_chain=chain,request_started_at=started,
                observed_at=stamp(),http_status=status,content_type=mime,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
    raise ValueError('ESEF_REDIRECT_LIMIT')


def execute(env):
    report=dict(ok=False,provider_requests=0,http_requests=0,model_calls=0,full_responses_archived=0,reports=[])
    stage='GUARDS';pending_write=False
    try:
        guard(env);shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        logging.getLogger('paramiko').disabled=True
        stage='SSH'
        with shared.access.ssh_client(config,{},paramiko) as transport:
            with shared.access.tunnel(transport,{}) as port:
                stage='BASELINE_SNAPSHOT';before=read_snapshot(env,port,TOTALS)
                preserved=[];totals=dict(TOTALS)
                for isin,obs,cur in PRESERVE:
                    a=asset(before,isin)
                    esef.need((len(a['facts']),len(a['current']))==(obs,cur),'PRESERVATION')
                    preserved.append(dict(isin=isin,name=a['name'],observations=obs,current=cur))
                for p in PROFILES:
                    a=asset(before,p['isin'])
                    esef.need(a['name'] in p['names'] and not a['facts'] and not a['current'],'TARGET_BASELINE')
                for profile in PROFILES:
                    item=dict(isin=profile['isin'],ok=False,provider_requests=0,http_requests=0);report['reports'].append(item)
                    a=asset(before,profile['isin']);identity=dict(isin=profile['isin'],name=a['name'])
                    selected=dict(identity=identity,preserve_assets=list(preserved),execution=profile['execution'],authorization=AUTH)
                    try:
                        stage='DB_PREFLIGHT';inspected,elapsed=shared.database(env,port,'inspect',selected=selected)
                        item['preflight_runner_ms']=elapsed
                        stage='PRIVATE_RESERVATION';reserved=shared.archive(transport,'reserve',env,selected=selected)
                        stage='ESEF_PACKAGE_GET';started=time.monotonic();raw,meta=download(profile,item)
                        item['provider_ms']=(time.monotonic()-started)*1000
                        meta.update(execution=profile['execution'],commit=env['GITHUB_SHA'])
                        stage='ESEF_QUALIFICATION';plan=esef.parse(raw,meta,identity,profile);del raw
                        stage='EVIDENCE_ARCHIVE';compact=plan['evidence_json'].encode('utf-8');stored=plan['stored_evidence']
                        shared.archive(transport,'archive',env,reserved['identity'],stored,compact,selected=selected)
                        plan['archive']=shared.archive(transport,'verify',env,reserved['identity'],stored,selected=selected)
                        item.update(response_sha256=meta['sha256'],response_bytes=meta['bytes'],evidence_sha256=stored['sha256'],
                            evidence_bytes=len(compact),evidence='PASS',periods=plan['reported_periods'],
                            currency=plan['units'][0]['monetary_currency_code'],data_gaps=plan['unqualified_metrics'])
                        stage='DB_APPLY_AND_READBACK';pending_write=True
                        result,elapsed=shared.database(env,port,'apply',selected=selected,baseline=inspected['baseline'],
                            protected=inspected['protected'],asset_id=inspected['asset_id'],plan=plan)
                        stage='FINAL_EVIDENCE_READBACK'
                        shared.archive(transport,'verify',env,reserved['identity'],stored,selected=selected)
                        pending_write=False;item.update(result,apply_runner_ms=elapsed)
                        totals['m2_fundamental_observations']+=result['observations'];totals['m2_fundamental_current']+=result['current']
                        preserved.append(dict(**identity,observations=result['observations'],current=result['current']))
                        del plan,compact
                    except Exception as exc:
                        item.update(stage=stage,error_code=safe_code(exc),outcome='UNKNOWN_NO_RETRY' if pending_write else 'STOP_NO_RETRY')
                        if isinstance(exc,RuntimeError) and str(exc) in {'INPUT','IDENTITY','SCHEMA6','PLAN','TRANSACTION','COMMIT','INDEPENDENT_READBACK'}:item['db_stage']=str(exc)
                        if pending_write: raise
                        # Only isolated source/qualification failures allow the other issuer.
                        if stage not in ('ESEF_PACKAGE_GET','ESEF_QUALIFICATION'): raise
                stage='INDEPENDENT_ANALYSIS_READBACK';final=read_snapshot(env,port,totals)
                target_isins={p['isin'] for p in PROFILES}
                for old in before['assets']:
                    isin=old['identifiers'][0]['normalized_value'];new=asset(final,isin)
                    if isin not in target_isins: esef.need(new==old,'PRESERVATION')
                    else: esef.need({k:v for k,v in new.items() if k not in ('facts','current')}=={k:v for k,v in old.items() if k not in ('facts','current')},'PRESERVATION')
                for profile,item in zip(PROFILES,report['reports']):
                    a=asset(final,profile['isin'])
                    if not item['ok']:
                        esef.need(not a['facts'] and not a['current'],'SNAPSHOT_BINDING');continue
                    s=build(a,final['sources']);prepare(s)
                    fields=('metric_key','value_decimal','unit_key','fiscal_year','period_start','period_end','field_path')
                    norm=lambda rows:sorted(tuple(esef.decimal(r[k]) if k=='value_decimal' else str(r[k]) for k in fields) for r in rows)
                    esef.need(norm(a['facts'])==norm(item['verified_facts']) and all(f['currency']==profile['expected_currency'] for f in s['facts']),'SNAPSHOT_BINDING')
                    item['analysis']=dict(contract=s['contract'],reference_check='PASS',calculations=s['calculations'],
                        missing_metrics=s['missing_metrics'],warnings=s['warnings'])
                count=sum(bool(a['facts']) for a in final['assets']);all_ok=all(r['ok'] for r in report['reports'])
                report.update(ok=all_ok,stage='SUCCESS' if all_ok else 'PARTIAL_SOURCE_GAPS',with_fundamentals=count,without_fundamentals=9-count,
                    validated_totals=final['validated_totals'],independent_analysis_readback='PASS',old_assets_unchanged=True,
                    market_unchanged=True,commit=env['GITHUB_SHA'])
    except Exception as exc:
        report.update(stage=stage,error_code=safe_code(exc),outcome='UNKNOWN_NO_RETRY' if pending_write else 'STOP_NO_RETRY')
    report['provider_requests']=sum(i['provider_requests'] for i in report['reports'])
    report['http_requests']=sum(i['http_requests'] for i in report['reports'])
    return report


if __name__=='__main__':
    result=execute(os.environ);print(shared.access.public_text(result,os.environ));sys.exit(0 if result['ok'] else 1)
