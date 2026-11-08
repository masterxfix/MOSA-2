"""Single manually authorized read-only DB analysis, no provider requests."""
from decimal import Decimal
import os,json,sys,subprocess,time
import re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals.analysis import build, SnapshotError, SNAPSHOT_CODES
from scripts.fundamentals_hkex_once import EXPECTED as HKEX_EXPECTED, PRESERVE as HKEX_PRESERVE

PHASES={'SSH_CONNECT','DB_CONNECT','SCHEMA_CHECK','ASSET_DISCOVERY','FUNDAMENTAL_READ','CURRENT_READ','SOURCE_READ','PERFORMANCE_CHECK','JSON_SERIALIZATION','SNAPSHOT_BUILD','READBACK_VALIDATION'}
ERRORS={'INVALID_UTF8_OR_JSON','DB_OPERATION_FAILED','VALIDATION_FAILED'}
HKEX_TOTALS={'m2_fundamental_observations':99,'m2_fundamental_current':50,'m2_market_observations':28,'m2_market_current':5}
HKEX_AUTH='MOSA2-HKEX-READONLY-20261102:'
ISIN_RE=re.compile(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$')

class ScopeValidationError(ValueError):
 pass

def scope_for(env):
 scope=env.get('MOSA_ANALYSIS_SCOPE','standard')
 if scope not in ('standard','hkex'):raise ValueError('ANALYSIS_SCOPE')
 return scope

def auth_prefix(scope):
 return HKEX_AUTH if scope=='hkex' else 'MOSA2-ANALYSIS:'

def target_isin(env):
 value=env.get('MOSA_ANALYSIS_ISIN','').strip()
 if not value:return None
 if not ISIN_RE.fullmatch(value):raise ValueError('ANALYSIS_ISIN')
 return value

def _assets_by_isin(assets):
 out={}
 for asset in assets:
  for identifier in asset['identifiers']:
   out.setdefault(identifier['normalized_value'],[]).append(asset)
 return out

def _normalized(value):
 return Decimal(str(value)).normalize()

def validate_hkex_snapshot(data,snapshots):
 if data.get('validated_totals')!=HKEX_TOTALS:raise ScopeValidationError('HKEX_TOTALS')
 if data.get('db_unchanged') is not True:raise ScopeValidationError('HKEX_DB_CHANGED')
 raw_by_isin=_assets_by_isin(data['assets'])
 snap_by_isin=_assets_by_isin([dict(identifiers=[dict(normalized_value=i) for i in s['identity']['isin']])|{'snapshot':s} for s in snapshots])
 if sum(bool(asset['facts']) for asset in data['assets'])!=9:raise ScopeValidationError('HKEX_ASSET_SCOPE')
 for preserved in HKEX_PRESERVE:
  matches=raw_by_isin.get(preserved['isin'],[])
  if len(matches)!=1 or matches[0]['name']!=preserved['name'] or len(matches[0]['facts'])!=preserved['observations'] or len(matches[0]['current'])!=preserved['current']:
   raise ScopeValidationError('HKEX_PRESERVATION')
 for expected in HKEX_EXPECTED['profiles'].values():
  matches=raw_by_isin.get(expected['isin'],[])
  snap_matches=snap_by_isin.get(expected['isin'],[])
  if len(matches)!=1 or len(snap_matches)!=1 or len(matches[0]['facts'])!=10 or len(snap_matches[0]['snapshot']['facts'])!=10 or len(snap_matches[0]['snapshot']['current_observation_ids'])!=5:
   raise ScopeValidationError('HKEX_TARGET_SCOPE')
  actual={(row['metric_key'],str(row['fiscal_year'])):_normalized(row['value_decimal']) for row in matches[0]['facts']}
  wanted={(metric,year):_normalized(value) for metric,periods in expected['values'].items() for year,value in periods.items()}
  if actual!=wanted:raise ScopeValidationError('HKEX_VALUES')
  if {year for metric,year in actual}!={'2024','2025'} or len({metric for metric,year in actual})!=5:raise ScopeValidationError('HKEX_PERIODS')
  for row in matches[0]['facts']:
   if row['unit_key']!='CNY_THOUSAND' or row['monetary_currency_code']!='CNY' or not row['fetch_id'] or not row['field_path'] or not isinstance(row['evidence_sha256'],str) or len(row['evidence_sha256'])!=64:
    raise ScopeValidationError('HKEX_REFERENCES')
  for row in snap_matches[0]['snapshot']['facts']:
   if row['unit']!='CNY_THOUSAND' or row['currency']!='CNY' or row['origin']=='unknown':raise ScopeValidationError('HKEX_SOURCE_REFERENCE')
 return dict(scope='hkex',target_companies=2,target_observations=20,target_current=10,preserved_companies=7,preserved_observations=79,preserved_current=40)

def execute(env):
    stage='GUARDS'
    try:
        scope=scope_for(env)
        isin=target_isin(env)
        shared.guard(env,dict(reusable_manual=True,authorization=auth_prefix(scope)))
        shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        stage='SSH_CONNECT'
        start=time.monotonic()
        with shared.access.ssh_client(config,{},paramiko) as transport:
            with shared.access.tunnel(transport,{}) as port:
                ssh_ms=(time.monotonic()-start)*1000
                stage='DB_CONNECT'
                request_data=dict(password=env['MOSA_TEST_DB_PASSWORD'],port=port)
                if scope=='hkex':request_data['expected_totals']=HKEX_TOTALS
                if isin is not None:request_data['isin']=isin
                p=subprocess.run(['php',str(shared.ROOT/'scripts/fundamentals/analysis_read.php')],input=json.dumps(request_data),text=True,capture_output=True,timeout=600)
                if p.stderr or len(p.stdout)>262144:raise ValueError('DB_PROCESS_FAILED')
                stage='JSON_SERIALIZATION'
                data=json.loads(p.stdout)
                if not data.get('ok'):
                    stage=data.get('phase') if data.get('phase') in PHASES else 'DB_CONNECT'
                    return dict(ok=False,stage=stage,error_code=data.get('error_code') if data.get('error_code') in ERRORS else 'DB_PROCESS_FAILED',provider_requests=0,db_writes=0)
                if p.returncode:raise ValueError('DB_PROCESS_FAILED')
        stage='SNAPSHOT_BUILD'
        snapshots=[build(a,data['sources']) for a in data['assets']]
        if isin is not None:
            matches=[s for s in snapshots if isin in s['identity']['isin']]
            if len(matches)!=1 or len(snapshots)!=1:raise ScopeValidationError('TARGET_ASSET_SCOPE')
        stage='READBACK_VALIDATION'
        for snapshot in snapshots:
            refs={f['observation_id'] for f in snapshot['facts']}
            if not all(set(c['observation_ids'])<=refs for c in snapshot['calculations']):raise ValueError('FACT_REFERENCE')
            if any(f['origin']=='unknown' for f in snapshot['facts']):raise ValueError('SOURCE_REFERENCE')
        hkex_summary=validate_hkex_snapshot(data,snapshots) if scope=='hkex' else None
        summaries=[dict(name=s['identity']['name'],observations=len(s['facts']),current=len(s['current_observation_ids']),metric_groups=len({f['metric'] for f in s['facts']}),calculation_types=sorted({c['kind'] for c in s['calculations']}),curated_rounded=any(f['rounded'] for f in s['facts'])) for s in snapshots]
        result=dict(ok=True,contract='mosa2-ai-analysis-input-v1',equities=len(snapshots),successful_snapshots=len(snapshots),with_fundamentals=sum(bool(s['facts']) for s in snapshots),without_fundamentals=sum(not s['facts'] for s in snapshots),excluded_etfs=data['excluded_etfs'],excluded_other=data['excluded_other'],db_unchanged=data['db_unchanged'],validated_totals=data['validated_totals'],fact_references='PASS',source_references='PASS',provider_requests=0,db_writes=0,model_calls=0,ssh_setup_ms=ssh_ms,performance=data['performance'],summary=summaries,read_only_confirmed=data.get('read_only_confirmed') is True,db_identity=data.get('db_identity'),market_data_read=data.get('market_data_read',True))
        if isin is not None:
            target=data['assets'][0]
            result.update(target_isin=isin,target_asset_count=len(snapshots),target_observations=len(snapshots[0]['facts']),target_current=len(snapshots[0]['current_observation_ids']),target_observation_rows=[{k:row[k] for k in ('id','metric_key','value_decimal','unit_key','unit_version','period_type','fiscal_year','fiscal_quarter','period_start','period_end','source_id','fetch_id','field_path','monetary_currency_code','parser_key','parser_version','parse_status','http_status','storage_backend','evidence_sha256')} for row in target['facts']],target_current_rows=target['current'],target_sources=data['sources'])
        if scope=='hkex':result.update(hkex_summary)
        return result
    except ScopeValidationError as error:
        return dict(ok=False,stage='READBACK_VALIDATION',error_code='VALIDATION_FAILED',provider_requests=0,db_writes=0)
    except Exception as error:
        code=str(error) if isinstance(error,SnapshotError) and str(error) in SNAPSHOT_CODES else ('SNAPSHOT_VALIDATION_FAILED' if stage=='SNAPSHOT_BUILD' else 'SAFE_PHASE_FAILURE')
        return dict(ok=False,stage=stage,error_code=code,provider_requests=0,db_writes=0)
if __name__=='__main__':
    r=execute(os.environ);print(shared.access.public_text(r,os.environ));sys.exit(0 if r['ok'] else 1)
