"""Single manually authorized read-only DB analysis, no provider requests."""
import os,json,sys,subprocess,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals.analysis import build

PHASES={'SSH_CONNECT','DB_CONNECT','SCHEMA_CHECK','ASSET_DISCOVERY','FUNDAMENTAL_READ','CURRENT_READ','SOURCE_READ','PERFORMANCE_CHECK','JSON_SERIALIZATION','SNAPSHOT_BUILD','READBACK_VALIDATION'}
ERRORS={'INVALID_UTF8_OR_JSON','DB_OPERATION_FAILED','VALIDATION_FAILED'}

def execute(env):
    stage='GUARDS'
    try:
        shared.guard(env,dict(reusable_manual=True,authorization='MOSA2-ANALYSIS:'))
        shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        stage='SSH_CONNECT'
        start=time.monotonic()
        with shared.access.ssh_client(config,{},paramiko) as transport:
            with shared.access.tunnel(transport,{}) as port:
                ssh_ms=(time.monotonic()-start)*1000
                stage='DB_CONNECT'
                p=subprocess.run(['php',str(shared.ROOT/'scripts/fundamentals/analysis_read.php')],input=json.dumps(dict(password=env['MOSA_TEST_DB_PASSWORD'],port=port)),text=True,capture_output=True,timeout=600)
                if p.stderr or len(p.stdout)>262144:raise ValueError('DB_PROCESS_FAILED')
                stage='JSON_SERIALIZATION'
                data=json.loads(p.stdout)
                if not data.get('ok'):
                    stage=data.get('phase') if data.get('phase') in PHASES else 'DB_CONNECT'
                    return dict(ok=False,stage=stage,error_code=data.get('error_code') if data.get('error_code') in ERRORS else 'DB_PROCESS_FAILED',provider_requests=0,db_writes=0)
                if p.returncode:raise ValueError('DB_PROCESS_FAILED')
        stage='SNAPSHOT_BUILD'
        snapshots=[build(a,data['sources']) for a in data['assets']]
        stage='READBACK_VALIDATION'
        for snapshot in snapshots:
            refs={f['observation_id'] for f in snapshot['facts']}
            if not all(set(c['observation_ids'])<=refs for c in snapshot['calculations']):raise ValueError('FACT_REFERENCE')
            if any(f['origin']=='unknown' for f in snapshot['facts']):raise ValueError('SOURCE_REFERENCE')
        summaries=[dict(name=s['identity']['name'],observations=len(s['facts']),current=len(s['current_observation_ids']),metric_groups=len({f['metric'] for f in s['facts']}),calculation_types=sorted({c['kind'] for c in s['calculations']}),curated_rounded=any(f['rounded'] for f in s['facts'])) for s in snapshots]
        return dict(ok=True,contract='mosa2-ai-analysis-input-v1',equities=len(snapshots),successful_snapshots=len(snapshots),with_fundamentals=sum(bool(s['facts']) for s in snapshots),without_fundamentals=sum(not s['facts'] for s in snapshots),excluded_etfs=data['excluded_etfs'],excluded_other=data['excluded_other'],db_unchanged=data['db_unchanged'],validated_totals=data['validated_totals'],fact_references='PASS',source_references='PASS',provider_requests=0,db_writes=0,model_calls=0,ssh_setup_ms=ssh_ms,performance=data['performance'],summary=summaries)
    except Exception:return dict(ok=False,stage=stage,error_code='SAFE_PHASE_FAILURE',provider_requests=0,db_writes=0)
if __name__=='__main__':
    r=execute(os.environ);print(shared.access.public_text(r,os.environ));sys.exit(0 if r['ok'] else 1)
