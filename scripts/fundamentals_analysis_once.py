"""Single manually authorized read-only DB analysis, no provider requests."""
import os,json,sys,subprocess,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals.analysis import build

def execute(env):
    stage='GUARDS'
    try:
        shared.guard(env,dict(reusable_manual=True,authorization='MOSA2-ANALYSIS:'))
        shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        stage='READ_ONLY_DB'
        start=time.monotonic()
        with shared.access.ssh_client(config,{},paramiko) as transport:
            with shared.access.tunnel(transport,{}) as port:
                ssh_ms=(time.monotonic()-start)*1000
                p=subprocess.run(['php',str(shared.ROOT/'scripts/fundamentals/analysis_read.php')],input=json.dumps(dict(password=env['MOSA_TEST_DB_PASSWORD'],port=port)),text=True,capture_output=True,timeout=600)
                if p.returncode or p.stderr or len(p.stdout)>262144:raise ValueError('DB_READ')
                data=json.loads(p.stdout)
                if not data['ok']:raise ValueError('DB_READ')
        stage='SNAPSHOTS'
        snapshots=[build(a,data['sources']) for a in data['assets']]
        # Compact summaries only; complete snapshots stay in ephemeral memory.
        summaries=[]
        for s,a in zip(snapshots,data['assets']):
            summaries.append(dict(identity=s['identity'],observations=len(s['facts']),current=len(s['current_observation_ids']),metrics=sorted({f['metric'] for f in s['facts']}),facts=s['facts'],periods=s['periods'],missing=s['missing_metrics'],sources=s['sources'],market_source_ids=s['market_source_ids'],warnings=s['warnings'],calculations=s['calculations']))
        return dict(ok=True,contract='mosa2-ai-analysis-input-v1',equities=len(snapshots),with_fundamentals=sum(bool(s['facts']) for s in snapshots),without_fundamentals=sum(not s['facts'] for s in snapshots),excluded_etfs=data['excluded_etfs'],excluded_other=data['excluded_other'],registered_sources_not_asset_availability=data['sources'],db_unchanged=data['db_unchanged'],provider_requests=0,db_writes=0,model_calls=0,ssh_setup_ms=ssh_ms,performance=data['performance'],summary=summaries)
    except Exception:return dict(ok=False,stage=stage,error='ANALYSIS_STOP_NO_RETRY',provider_requests=0,db_writes=0)
if __name__=='__main__':
    r=execute(os.environ);print(shared.access.public_text(r,os.environ));sys.exit(0 if r['ok'] else 1)
