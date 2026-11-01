"""One explicitly authorized Dogado-side API call, key never crosses SSH."""
import json,os,sys,shlex
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals_assessment_once import read_db,PRICE
from scripts.fundamentals.assessment import prepare,need

WORKFLOW='.github/workflows/fundamentals-assessment-existing-mosa-once.yml'
def remote_pilot(ssh,env,snapshot):
    library=shared.directories.REMOTE_SOURCE.split('\nif __name__=="__main__":')[0]
    archive=(shared.ROOT/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8').split("\nif __name__ == '__main__':")[0]
    marker=(shared.ROOT/'scripts/fundamentals/assessment_once_remote.py').read_text(encoding='utf-8').split("\nif __name__=='__main__':")[0]
    source=library+'\n'+archive+'\n'+marker+'\n'+(shared.ROOT/'scripts/fundamentals/assessment_dogado_remote.py').read_text(encoding='utf-8')
    sha=prepare(snapshot)[1]
    data=dict(snapshot=snapshot,price=PRICE,invocation_id='mosa2-dogado-ai-'+env['GITHUB_RUN_ID'],
        modules={n:(shared.ROOT/('scripts/fundamentals/'+n+'.py')).read_text(encoding='utf-8') for n in ('assessment','responses_transport')},
        marker=dict(execution='fundamentals-ai-droneshield-existing-mosa-20261101-01',commit=env['GITHUB_SHA'],isin='AU000000DRO2',input_digest=sha,model='gpt-6.1-sol',workflow=WORKFLOW))
    payload=json.dumps(data).encode();need(len(payload)<=65536,'REMOTE_INPUT_BOUND')
    code,out,err,_=shared.remote.remote_call(ssh,shlex.join([shared.directories.PYTHON,'-I','-B','-c',source]),payload,timeout=150)
    need(not code and not err and len(out)<=8192,'REMOTE_PROCESS_FAILED')
    result=json.loads(out)
    allowed={'security_risk','interpretation_details','uncertainties','missing_information','reasoning','input_digest_verified','config_metadata','protection_policy','ok','model_calls','key_transferred','db_writes','cost_status','server_key_usable','response_status','actual_model','usage','cost_upper_bound','input_digest','structured_output','fact_references','calculation_references','source_binding','interpretation_codes','facts','calculations','actual_cost_upper_bound_usd','stage','mosa_unchanged','error_code'}
    need(type(result) is dict and set(result)<=allowed,'REMOTE_RESULT_SHAPE')
    if result.get('ok'):need(result.get('input_digest')==sha and result.get('model_calls')==1 and result.get('key_transferred') is False,'REMOTE_RESULT_BINDING')
    return result

def execute(env):
    result=dict(ok=False,model_calls=0,key_transferred=False,db_writes=0,provider_requests=0);stage='GUARDS'
    try:
        shared.guard(env,dict(authorization='MOSA2-DRONESHIELD-EXISTING-MOSA-AI-ONCE-20261101:'))
        need(env.get('GITHUB_WORKFLOW_REF')=='masterxfix/MOSA-2/'+WORKFLOW+'@refs/heads/main','WORKFLOW_BINDING')
        shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        stage='SSH_CONNECT'
        with shared.access.ssh_client(config,{},paramiko) as ssh:
            with shared.access.tunnel(ssh,{}) as port:
                stage='DB_READ';snapshot=read_db(env,port);sha=prepare(snapshot)[1];result['db_unchanged']=True
                stage='DOGADO_PROCESS';result.update(remote_pilot(ssh,env,snapshot))
                if not result.get('ok'):return result
                stage='FINAL_DB_READBACK';after=read_db(env,port);need(prepare(after)[1]==sha,'DB_CHANGED')
        result.update(ok=True,stage='SUCCESS')
    except Exception:
        result.update(ok=False,stage=stage,error_code='RUNNER_STOP_NO_RETRY')
        if stage=='DOGADO_PROCESS':result.update(model_calls='UNKNOWN_NO_RETRY',cost_status='UNKNOWN')
    return result
if __name__=='__main__':
    r=execute(os.environ);print(shared.access.public_text(r,os.environ));sys.exit(0 if r['ok'] else 1)
