"""PREPARE only: exact schema audit and non-executable migration plan. No DB driver."""
import functools
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT/'docs/database/migrations/0005_collector_reservations.sql'
EXPECTED_SHA = '2521552c548370806bc311798f12be39f16b102733aeb74ac9c01337e7e46333'
TABLES = ['m2_collector_state','m2_collector_cycles','m2_collector_days','m2_collector_requests']

def unpack(envelope):
    if envelope.get('encoding')!='gzip-base64-v1' or type(envelope.get('length')) is not int or not 0<envelope['length']<=2000000:raise ValueError('METADATA_ENCODING_REJECTED')
    if not isinstance(envelope.get('payload'),str) or len(envelope['payload'])>65536:raise ValueError('METADATA_ENCODING_REJECTED')
    packed=base64.b64decode(envelope['payload'],validate=True)
    decoder=zlib.decompressobj(31);raw=decoder.decompress(packed,2000001)
    if len(raw)!=envelope['length'] or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or hashlib.sha256(raw).hexdigest()!=envelope['sha256']:raise ValueError('METADATA_INTEGRITY_REJECTED')
    return json.loads(raw)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def current_binding(snapshot):
    # Acquisition/market timestamps are facts; the inspection clock is not baseline drift.
    return [dict(isin=e['isin'],scope_rows=e['scope_rows'],
                 input={k:v for k,v in (e['input'] or {}).items() if k not in ('now','approval')}) for e in snapshot['items']]

def php(request):
    # Existing historical schema generators require the original numbered SQL aliases.
    with tempfile.TemporaryDirectory() as folder:
        for n in range(1,4):
            source=next((ROOT/'docs/database/migrations').glob(f'{n:04d}_*.sql'))
            (Path(folder)/f'{n:04d}.sql').write_bytes(source.read_bytes())
        p=subprocess.run(['php',str(ROOT/'scripts/market_collector/migration5_audit.php'),folder],
                         input=json.dumps(request),capture_output=True,text=True,timeout=30)
    if p.returncode or p.stderr:
        raise ValueError('SCHEMA_AUDIT_PROCESS_REJECTED')
    reply=json.loads(p.stdout)
    if reply.get('ok') is not True:
        raise ValueError(reply.get('code','EXACT_SCHEMA_REJECTED'))
    return reply['result']

@functools.lru_cache(maxsize=1)
def contract():
    if hashlib.sha256(MIGRATION.read_bytes()).hexdigest()!=EXPECTED_SHA:
        raise ValueError('MIGRATION_ARTIFACT_REJECTED')
    return php(dict(operation='contract'))

def tables(data):
    rows=data['inventory'][0]
    if rows['sql']!='SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME' or rows['args']:
        raise ValueError('TABLE_EVIDENCE_REJECTED')
    return [r['TABLE_NAME'] for r in rows['rows']]

def assess(data):
    """All non-exact/partial states block. Presence mask is diagnostic, never a resume point."""
    try:
        c=contract();names=tables(data);new=[t for t in TABLES if t in names]
        properties=data['properties']
        if properties['db']!='h29077_mosa2_test' or not re.fullmatch(r'8\.0\.\d+(?:[-.][A-Za-z0-9.-]+)?',properties['version']) or str(properties['fk_checks'])!='1':raise ValueError('DATABASE_PROPERTIES_REJECTED')
        markers=dict(tables=new,job=bool(data['jobs']),module=bool(data['modules']),
                     ledger5=any(str(r['version'])=='5' for r in data['ledger']),bootstrap=bool(data['collector'].get(TABLES[0])))
        if names==c['envelope4']['tables'] and not any([new,data['jobs'],data['modules'],markers['ledger5']]):version=4
        elif names==c['envelope5']['tables'] and markers['ledger5']:version=5
        else:return dict(status='PARTIAL_OR_CONFLICT',apply_allowed=False,markers=markers)
        ledger=data['ledger'];keys=[f'{n:04d}_'+['core_asset_identity','market_current_history','market_units','current_observation_provenance','collector_reservations'][n-1] for n in range(1,version+1)]
        if ([str(r['version']) for r in ledger]!=c[f'envelope{version}']['versions'] or
            [r['migration_key'] for r in ledger]!=keys or
            [r['checksum'].lower() for r in ledger]!=c[f'envelope{version}']['digests'] or
            set(data['objects'])!={'routines','triggers','events'} or any(int(v)!=0 for v in data['objects'].values())):
            raise ValueError('LEDGER_OR_OBJECT_CONFLICT')
        php(dict(operation='audit',inventory=data['inventory'],version=version))
        if version==5:
            if len(data['jobs'])!=1 or len(data['modules'])!=1:raise ValueError('ANCHOR_CONFLICT')
            job=data['jobs'][0];module=data['modules'][0]
            if {k:str(job[k]) for k in ('job_key','module_key','handler_key','enabled')}!=dict(job_key='collector_reservations_v1',module_key='collector_reservations',handler_key='UNWIRED',enabled='0'):raise ValueError('JOB_CONFLICT')
            if {k:str(module[k]) for k in ('module_key','schema_version','status')}!=dict(module_key='collector_reservations',schema_version='5',status='LOCKED'):raise ValueError('MODULE_CONFLICT')
            state=data['collector'].get(TABLES[0],[])
            if len(state)!=1:raise ValueError('BOOTSTRAP_CONFLICT')
            expected=dict(provider='boerse_frankfurt_api_v1',job_id=str(job['id']),status='IDLE',stop_latched='1',unresolved='0',
                          active_cycle=None,last_confirmed_cycle=None,pending_asset=None,operation_token=None,last_observed_utc=None,error_code='INITIAL_LOCK')
            if {k:None if v is None else str(v) for k,v in state[0].items()}!=expected or any(data['collector'].get(t) for t in TABLES[1:]):raise ValueError('BOOTSTRAP_CONFLICT')
        return dict(status='SCHEMA4_READY' if version==4 else 'SCHEMA5_LOCKED_COMPLETE',apply_allowed=False,markers=markers)
    except Exception:
        return dict(status='UNKNOWN_OR_DRIFT',apply_allowed=False)

def prepare(data,revision,run_id,current_proof):
    state=assess(data)
    if state['status']!='SCHEMA4_READY' or not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('PREPARE_BASELINE_REJECTED')
    c=contract()
    return dict(contract='mosa2-migration5-prepare-v1',run_id=run_id,revision=revision,database='h29077_mosa2_test',
        migration_sha256=EXPECTED_SHA,source_schema=4,target_schema=5,baseline_sha256=digest(data),baseline=data,
        expected_schema=c['schemas5'],expected_ledger=c['envelope5'],current_proof=current_proof,
        steps=[dict(ordinal=i+1,sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),kind='AUTO_COMMIT_DDL' if i<5 else 'LOCKED_BOOTSTRAP_DML') for i,sql in enumerate(c['statements'])],
        ledger_step=dict(version=5,migration_key='0005_collector_reservations',checksum=EXPECTED_SHA,atomic_with_bootstrap=True),
        collector=dict(execution_enabled=False,budget_execution_enabled=False,rights_confirmed=False,job_enabled=False,module_status='LOCKED',stop_latched=True),
        backup_required='ENCRYPTED_ALL_SCHEMA4_TABLES_AND_SCHEMA_PLUS_LEDGER_JOBS_MODULE_STATE; ISOLATED_RESTORE_AND_SHA256_REQUIRED',
        verification='FRESH_BASELINE_COMPARE; EXACT_SCHEMA5; OLD_TABLE_ROW_HASHES; CURRENT_PROVENANCE; INDEPENDENT_READ_ONLY_CONNECTION',
        interruption_policy='STOP_NO_RETRY_NO_REPAIR_NO_DROP; READ_ONLY_TABLE_ANCHOR_LEDGER_MASK_AND_EXACT_METADATA',
        consumed_claim_required=True,automatic_retry=False,execution_authorized=False,
        blockers=['EXPLICIT_MIGRATION_AUTHORIZATION_MISSING','VERIFIED_BACKUP_AND_ISOLATED_RESTORE_MISSING',
                  'INSTALLED_COLLECTOR_SCHEMA5_COMPATIBILITY_NOT_CONFIRMED_NO_DEPLOYMENT_AUTHORIZED','FRESH_EXECUTION_PREFLIGHT_REQUIRED',
                  'COMPLETE_TRIGGER_ROUTINE_EVENT_VISIBILITY_NOT_PROVEN_WITH_SELECT_ONLY_ACCOUNT'])
