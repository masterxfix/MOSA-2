"""Versioned manually reviewed facts -> shared plan + private evidence. No network/SQL."""
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import re
from urllib.parse import urlsplit

METHOD = 'manually_reviewed_public_facts'
PARSER = 'curated_public_facts_v1'


def need(condition, code):
    if not condition: raise ValueError(code)


def url(value):
    need(isinstance(value,str) and len(value)<=2048, 'CURATED_SOURCE')
    parsed=urlsplit(value)
    need(parsed.scheme=='https' and bool(parsed.hostname) and parsed.username is None and parsed.password is None
         and parsed.port in (None,443) and not parsed.fragment, 'CURATED_SOURCE')
    return parsed


def load(raw, imported_at, identity):
    need(type(raw) is bytes and 0<len(raw)<=65536, 'CURATED_BOUND')
    def unique(pairs):
        result={}
        for key,value in pairs:
            need(key not in result,'CURATED_DUPLICATE_KEY');result[key]=value
        return result
    def invalid_number(value): raise ValueError('CURATED_DECIMAL_STRING')
    manifest=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_float=invalid_number,parse_constant=invalid_number)
    primary_review=manifest['format']=='mosa2-curated-facts-v2'
    need((primary_review or manifest['format']=='mosa2-curated-facts-v1') and manifest['input_method']==METHOD,'CURATED_FORMAT')
    need(re.fullmatch(r'[a-z][a-z0-9_-]{0,95}',manifest['manifest_id']) is not None,'CURATED_ID')
    need(manifest['issuer']==identity and re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]',identity['isin']) is not None,'CURATED_IDENTITY')
    now=datetime.strptime(imported_at,'%Y-%m-%d %H:%M:%S.%f')
    research=manifest['research']
    need(research['review_status']==('primary_document_manually_verified' if primary_review else 'user_attested_manually_reviewed') and research['independently_refetched_by_runner'] is False,'CURATED_REVIEW')
    if research['researched_at'] is None:
        need(research['time_status']=='before_assignment_exact_time_unknown','CURATED_RESEARCH_TIME')
    else:
        need(research['time_status']=='known_utc' and datetime.strptime(research['researched_at'],'%Y-%m-%d %H:%M:%S.%f')<=now,'CURATED_RESEARCH_TIME')
    source=manifest['source'];primary=url(manifest['primary_url']);base=url(source['base_url'])
    need(source['source_type']==METHOD and source['enabled']=='0' and primary.hostname==base.hostname
         and manifest['primary_url'].startswith(source['base_url'])
         and manifest['source_classification']==('issuer_primary_document' if primary_review else 'independent_third_party_report_reproduction'),'CURATED_SOURCE')
    for reference in manifest['comparison_sources']:
        url(reference['url']);need(reference['role']=='user_reported_comparison_only','CURATED_SOURCE')
    metrics={m['metric_key']:m for m in manifest['metrics']};units={u['unit_key']:u for u in manifest['units']}
    need(1<=len(metrics)==len(manifest['metrics'])<=64 and 1<=len(units)==len(manifest['units'])<=64,'CURATED_CATALOG')
    periods=manifest['periods'];need(1<=len(periods)<=16,'CURATED_PERIOD')
    for p in periods.values():
        base_keys={'period_type','fiscal_year','fiscal_quarter','period_start','period_end'}
        if p['period_type']=='snapshot':
            need(primary_review and set(p)==base_keys|{'as_of_at'} and all(p[k] is None for k in base_keys-{'period_type'}),'CURATED_PERIOD')
            stamp=datetime.strptime(p['as_of_at'],'%Y-%m-%d %H:%M:%S.%f')
            need(stamp.strftime('%Y-%m-%d 00:00:00.000000')==p['as_of_at'] and stamp<=now,'CURATED_PERIOD')
        else:
            need(set(p)==base_keys and p['period_type'] in ('fy','fq') and date.fromisoformat(p['period_start'])<date.fromisoformat(p['period_end'])<=now.date(),'CURATED_PERIOD')
    rows=manifest['facts'];need(1<=len(rows)<=256,'CURATED_BOUND');seen=set();observations=[];facts=[]
    publish_current=manifest.get('publish_current',True)
    need(type(publish_current) is bool and (publish_current or primary_review),'CURATED_PERIOD')
    for i,f in enumerate(rows):
        key=f['metric_key'];period=f['period'];unit=f['unit_key'];value=f['value']
        need(key in metrics and period in periods and unit in units,'CURATED_FACT_BINDING')
        need((key,period) not in seen,'CURATED_DUPLICATE_FACT');seen.add((key,period))
        need(type(value) is str and re.fullmatch(r'-?(?:0|[1-9][0-9]{0,25})(?:\.[0-9]{1,12})?',value) is not None,'CURATED_DECIMAL_STRING')
        need(Decimal(value).is_finite(),'CURATED_DECIMAL_STRING')
        need((type(f['rounded']) is bool if primary_review else f['rounded'] is True) and type(f['decimal_places']) is int and 0<=f['decimal_places']<=12
             and len(value.partition('.')[2])==f['decimal_places'],'CURATED_PRECISION')
        for field in ('original_label','original_unit','section','column'):
            need(isinstance(f[field],str) and 0<len(f[field])<=255,'CURATED_LOCATOR')
        need(f['validation_status']=='manually_reviewed' and f['original_unit']==units[unit]['display_name'],'CURATED_FACT_BINDING')
        dimension=metrics[key]['dimension_key']
        need(units[unit]['dimension_key']==dimension and
             ((dimension=='monetary' and units[unit]['monetary_currency_code'] is not None) or
              (primary_review and dimension=='share_count' and units[unit]['monetary_currency_code'] is None and f['decimal_places']==0 and Decimal(value)>=0)),'CURATED_UNIT')
        p=periods[period]
        need(publish_current or p['period_type']=='snapshot','CURATED_PERIOD')
        if primary_review:
            need(isinstance(f['locator'],str) and 0<len(f['locator'])<=255,'CURATED_LOCATOR')
        provenance={k:p[k] for k in ('period_start','period_end','fiscal_year')}
        if primary_review:provenance.update(period_type=p['period_type'],fiscal_quarter=p['fiscal_quarter'],as_of_at=p.get('as_of_at'))
        row=dict(metric_key=key,value_decimal=format(Decimal(value),'f'),unit_key=unit,unit_version=units[unit]['unit_version'],
            **({'as_of_at':None}|p),estimate_horizon=None,reported_at=None,observed_at=imported_at,value_type='decimal',
            dimension_key=dimension,value_text=None,value_date=None,field_path=f'curated-evidence:facts/{i};manifest:facts/{i}')
        observations.append(row)
        facts.append(dict(f,**provenance,
                          normalized_value=row['value_decimal'],normalized_unit=unit,validation_status='qualified_curated'))
    need(set(metrics)=={r['metric_key'] for r in rows} and set(units)=={r['unit_key'] for r in rows},'CURATED_UNUSED_CATALOG')
    meta=dict(input_method=METHOD,payload_kind='curated_manifest',url=manifest['primary_url'],observed_at=imported_at,
              http_status=None,content_type='application/json',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    doc=dict(format='mosa2-curated-evidence-v1',kind='curated_evidence',input_method=METHOD,
        http_request_performed=False,http_response=None,imported_at=imported_at,research=research,
        issuer=identity,source_url=manifest['primary_url'],source_classification=manifest['source_classification'],
        comparison_sources=manifest['comparison_sources'],input_manifest=meta,manifest_json=raw.decode('utf-8'),
        parser=dict(key=PARSER,version='2' if primary_review else '1'),facts=facts)
    compact=json.dumps(doc,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    need(len(compact)<=131072,'CURATED_BOUND')
    stored=dict(kind='curated_evidence',content_type='application/json',sha256=hashlib.sha256(compact).hexdigest(),bytes=len(compact),observed_at=imported_at)
    plan=dict(fiscal_year_start_month=manifest['fiscal_year_start_month'],parser_key=PARSER,parser_version=doc['parser']['version'],parse_status='parsed',
        source=source,metrics=manifest['metrics'],units=manifest['units'],observations=observations,
        metadata=meta,stored_evidence=stored,evidence_json=compact.decode('utf-8'))
    if primary_review:plan['publish_current']=publish_current
    return plan,compact,stored
