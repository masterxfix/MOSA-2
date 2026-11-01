"""One authorized real Responses pilot, read-only DB, no provider collection or retry."""
import json,os,sys,subprocess,shlex,re
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals.analysis import build
from scripts.fundamentals.assessment import ResponsesAdapter,AssessmentError,prepare,validate,canonical,need
from scripts.fundamentals.responses_transport import OpenAIResponsesTransport
PRICE=dict(model='gpt-6.1-sol',input_per_million='2.75',output_per_million='11',checked_at='2026-11-01T15:08:14+00:00',source_url='https://developers.openai.com/api/docs/models/gpt-6.1-sol')

def read_db(env,port):
    r=subprocess.run(['php',str(shared.ROOT/'scripts/fundamentals/analysis_read.php')],input=json.dumps(dict(password=env['MOSA_TEST_DB_PASSWORD'],port=port)),text=True,capture_output=True,timeout=600)
    need(not r.stderr and len(r.stdout)<=262144 and r.returncode==0,'DB_READ_FAILED')
    data=json.loads(r.stdout);need(data.get('ok') is True and data.get('db_unchanged') is True,'DB_READ_FAILED')
    matches=[a for a in data['assets'] if any(i['normalized_value']=='AU000000DRO2' for i in a['identifiers'])]
    need(len(matches)==1,'PILOT_IDENTITY');a=matches[0]
    snapshot=build(a,data['sources'])
    need(len(a['facts'])==14 and len(snapshot['current_observation_ids'])==7 and len({f['metric'] for f in snapshot['facts']})==7,'PILOT_COUNTS')
    for f in snapshot['facts']:
        need((f['start'],f['end']) in [('2025-01-01','2025-12-31'),('2024-01-01','2024-12-31')] and f['period_type']=='fy' and f['currency']=='AUD' and f['unit']=='AUD_MILLION','PILOT_PERIOD_UNIT')
        need(f['origin']=='manually_reviewed_public_facts' and f['rounded'] is True,'PILOT_ORIGIN')
    prepare(snapshot)
    return snapshot

def reserve(ssh,env,sha):
    library=shared.directories.REMOTE_SOURCE.split('\nif __name__=="__main__":')[0]
    archive=(shared.ROOT/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8').split("\nif __name__ == '__main__':")[0]
    source=library+'\n'+archive+'\n'+(shared.ROOT/'scripts/fundamentals/assessment_once_remote.py').read_text(encoding='utf-8')
    request=dict(execution='fundamentals-ai-droneshield-20261101-01',commit=env['GITHUB_SHA'],isin='AU000000DRO2',model='gpt-6.1-sol',input_digest=sha,workflow='.github/workflows/fundamentals-assessment-once.yml')
    code,out,err,_=shared.remote.remote_call(ssh,shlex.join([shared.directories.PYTHON,'-I','-B','-c',source]),json.dumps(request).encode(),timeout=60)
    need(not code and not err,'MARKER_FAILED');need(json.loads(out).get('ok') is True,'MARKER_FAILED')

class ObservedTransport:
    is_live=True
    def __init__(self,key,report):self.inner=OpenAIResponsesTransport(key,live_authorized=True);self.report=report
    def __call__(self,request,**options):
        self.report['model_calls']=1 # consumed attempt, also if outcome is unknown
        response=self.inner(request,**options)
        self.report.update(response_status=response.get('status'),actual_model=response.get('model'),usage=response.get('usage'),response_id=response.get('id'),cost_status='UNKNOWN_UNTIL_VALIDATED')
        usage=response.get('usage')
        if type(usage) is dict and all(type(usage.get(k)) is int and usage[k]>=0 for k in ('input_tokens','output_tokens')):
            self.report['actual_cost_upper_bound_usd']=str((Decimal(usage['input_tokens'])*Decimal(PRICE['input_per_million'])+Decimal(usage['output_tokens'])*Decimal(PRICE['output_per_million']))/1000000)
            self.report['cost_status']='ESTIMATE_UNVALIDATED_RESPONSE'
        return response

def execute(env):
    report=dict(ok=False,model_calls=0,db_writes=0,provider_requests=0,cost_status='NOT_CALLED');stage='GUARDS'
    try:
        shared.guard(env,dict(authorization='MOSA2-DRONESHIELD-AI-ONCE-20261101:'))
        need(env.get('GITHUB_WORKFLOW_REF')=='masterxfix/MOSA-2/.github/workflows/fundamentals-assessment-once.yml@refs/heads/main','WORKFLOW_BINDING')
        need(bool(env.get('MOSA2_OPENAI_API_KEY')),'SECRET_MISSING')
        shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        stage='SSH_CONNECT'
        with shared.access.ssh_client(config,{},paramiko) as ssh:
            with shared.access.tunnel(ssh,{}) as port:
                stage='READ_ONLY_SNAPSHOT';snapshot=read_db(env,port);p,sha=prepare(snapshot)
                report.update(input_digest=sha,db_unchanged=True)
                stage='API_PREFLIGHT'
                def preflight(request,budget,prepared,meta):
                    nonlocal stage
                    # Validate a complete exact echo offline against the real snapshot.
                    expected=dict(meta,factual_claims=[dict(observation_id=f['observation_id'],metric_key=f['metric'],value=f['value'],unit_key=f['unit'],source_id=f['source_id'],origin=f['origin'],rounded=f['rounded']) for f in prepared['facts']],calculation_claims=[dict(calculation_id=c['calculation_id'],value=c['value']) for c in prepared['calculations']])
                    validate(expected,prepared,sha,meta['model_id'],meta['invocation_id'],meta['generated_at'])
                    # Generous output cap for complete echo plus reasoning. Reject oversized echo.
                    need(len(canonical(expected).encode())<=12000,'OUTPUT_PREFLIGHT_BOUND')
                    report.update(cost_upper_bound=budget,expected_echo_bytes=len(canonical(expected).encode()))
                    stage='PRIVATE_RESERVATION'
                    reserve(ssh,env,sha)
                    stage='MODEL_POST_AND_VALIDATION'
                adapter=ResponsesAdapter(ObservedTransport(env['MOSA2_OPENAI_API_KEY'],report),max_output_tokens=4000)
                result=adapter.assess(snapshot,price=PRICE,now=datetime.now(timezone.utc),invocation_id='mosa2-ai-once-'+env['GITHUB_RUN_ID'],authorized_digest=sha,preflight=preflight)
                stage='OUTPUT_VALIDATED'
                assessment=result['assessment'];need(bool(assessment['interpretations']),'INTERPRETATIONS_MISSING')
                report.update(structured_output='PASS',input_digest_verified='PASS',fact_references='PASS',calculation_references='PASS',source_binding='PASS',facts=len(assessment['factual_claims']),calculations=len(assessment['calculation_claims']),interpretation_codes=sorted({x['code'] for x in assessment['interpretations']}),actual_cost_upper_bound_usd=result['actual_cost_upper_bound_usd'],cost_status='CONSERVATIVE_ESTIMATE',usage=result['usage'])
                stage='FINAL_DB_READBACK';after=read_db(env,port);need(prepare(after)[1]==sha,'DB_CHANGED')
        report.update(ok=True,stage='SUCCESS')
    except Exception as error:
        allowed={'PILOT_IDENTITY','PILOT_COUNTS','PILOT_PERIOD_UNIT','PILOT_ORIGIN','DB_READ_FAILED','MARKER_FAILED','WORKFLOW_BINDING','SECRET_MISSING','OUTPUT_PREFLIGHT_BOUND','INTERPRETATIONS_MISSING','DB_CHANGED','INPUT_TOKEN_BOUND','COST_LIMIT','STALE_PRICE','MODEL_TRANSPORT_FAILED','MODEL_INCOMPLETE','MODEL_REFUSAL_OR_TOOL','OUTPUT_SCHEMA','INPUT_DIGEST','INVOCATION_BINDING','FACT_REFERENCE','FACT_BINDING','INCOMPLETE_FACTS','CALCULATION_REFERENCE','CALCULATION_BINDING','INCOMPLETE_CALCULATIONS','INTERPRETATION_REFERENCE','INTERPRETATION_BINDING','MISSING_BINDING','USAGE_MISSING','USAGE_INVALID','USAGE_OVER_BUDGET'}
        report.update(stage=stage,error_code=str(error) if isinstance(error,AssessmentError) and str(error) in allowed else 'PILOT_STOP_NO_RETRY',outcome='NO_RETRY')
    # Only bounded approved metadata can reach public logs, even after malformed provider output.
    if report.get('actual_model') not in (None,'gpt-6.1-sol'):report['actual_model']='UNEXPECTED_MODEL'
    if report.get('response_status') not in (None,'completed','incomplete','failed','cancelled','queued','in_progress'):report['response_status']='UNEXPECTED_STATUS'
    if not isinstance(report.get('response_id',''),str) or re.fullmatch(r'resp_[A-Za-z0-9_-]{1,120}',report.get('response_id','')) is None:report.pop('response_id',None)
    if 'usage' in report:
        usage=report['usage'];report['usage']={k:usage[k] for k in ('input_tokens','output_tokens','total_tokens') if type(usage) is dict and type(usage.get(k)) is int}
    return report
if __name__=='__main__':
    result=execute(os.environ);public=shared.access.public_text(result,os.environ)
    key=os.environ.get('MOSA2_OPENAI_API_KEY','')
    print(public if not key or key not in public else '{"ok":false,"error_code":"SECRET_OUTPUT_BLOCKED"}')
    sys.exit(0 if result['ok'] else 1)
