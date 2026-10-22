"""Exact pending Current takeover. No database or provider access."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.market_current import planner, preview

CONTRACT='mosa2-current-once-v1'
# Permanent historical tombstone, independent of seven-day artifact retention.
# Reconcile may still read this plan as evidence; it never calls approvals().
CONSUMED_RUN_IDS=frozenset({'current-once-39634298612'})

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def bound(entry):
    data=copy.deepcopy(entry['input'])
    data.pop('now',None);data.pop('approval',None)
    return dict(isin=entry['isin'],name=entry['name'],scope_rows=entry['scope_rows'],input=data)

def prepare(snapshot,run_id,revision):
    planner.require(run_id.startswith('current-once-') and len(run_id)<100,'takeover_run_id')
    planner.require(len(revision)==40 and all(c in '0123456789abcdef' for c in revision),'takeover_revision')
    report=preview.snapshot_preview(snapshot)
    items=[]
    for entry,result in zip(snapshot['items'],report['reports']):
        planner.require(result.get('candidate_decision') in ('UPDATE','INSERT'),'takeover_candidate')
        route=entry['input']['route']
        items.append(dict(reference=bound(entry),route_sha256=planner.route_hash(route),
            observation_id=result['latest_observation']['observation_id'],decision=result['candidate_decision'],
            disabled_projection_required=route['enabled']=='0'))
    planner.require(sorted(x['decision'] for x in items)==['INSERT']*3+['UPDATE']*2,'takeover_expected_counts')
    expires=(datetime.strptime(snapshot['as_of'],'%Y-%m-%d %H:%M:%S.%f')+timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S.%f')
    return dict(contract=CONTRACT,run_id=run_id,revision=revision,as_of=snapshot['as_of'],expires_at=expires,
        status='PENDING_EXPLICIT_AUTHORIZATION',authorization=None,items=items)

def phrase(plan):
    return 'EXECUTE_CURRENT_ONCE:'+plan['run_id']+':'+digest(plan)+':ALLOW_DISABLED_ROUTE_PROJECTION'

def approvals(plan,authorization,now):
    planner.require(plan['run_id'] not in CONSUMED_RUN_IDS,'takeover_consumed')
    planner.require(plan['contract']==CONTRACT and plan['status']=='PENDING_EXPLICIT_AUTHORIZATION'
        and plan['authorization'] is None,'takeover_pending_required')
    planner.require(authorization==phrase(plan),'takeover_explicit_authorization_required')
    planner.require(plan['as_of']<=now<=plan['expires_at'],'takeover_expired_or_clock')
    planner.require(len(plan['items'])==5,'takeover_scope')
    result=[]
    for item in plan['items']:
        route=item['reference']['input']['route']
        planner.require(item['route_sha256']==planner.route_hash(route),'takeover_route_hash')
        result.append(dict(route_id=route['id'],route_sha256=item['route_sha256'],approved_at=now,
            allow_disabled_projection=item['disabled_projection_required'] is True))
    return result

def validate(items,takeover):
    plan=takeover['plan'];authorization=takeover['authorization']
    planner.require(len(items)==5,'takeover_scope')
    planner.require(all(x['now']==items[0]['now'] for x in items),'takeover_snapshot_clock')
    approved=approvals(plan,authorization,items[0]['now'])
    planner.require(sorted(x['decision'] for x in plan['items'])==['INSERT']*3+['UPDATE']*2,'takeover_expected_counts')
    seen=set();plans=[]
    for data,expected,approval in zip(items,plan['items'],approved):
        data=copy.deepcopy(data);entry=data.pop('qualified_scope')
        entry['input']=copy.deepcopy(data)
        planner.require(bound(entry)==expected['reference'],'takeover_database_drift')
        planner.require(entry['isin'] not in seen,'takeover_duplicate_scope');seen.add(entry['isin'])
        # Existing qualification and Current planner retain all native-v2 checks.
        preview.php(entry,Path(__file__).with_name('preview_read.php'))
        data['approval']=approval
        result=planner.plan(data)
        planner.require(result['decision']==expected['decision'],'takeover_decision_drift')
        planner.require(result['values']['observation_id']==expected['observation_id'],'takeover_observation_drift')
        plans.append(result)
    scope=preview.php(dict(operation='scope'),Path(__file__).with_name('preview_read.php'))['scope']
    planner.require(seen==set(scope),'takeover_scope')
    return plans

if __name__=='__main__':
    try:
        data=json.loads(sys.stdin.read());result=validate(data['items'],data['takeover'])
        print(json.dumps(dict(ok=True,plans=result)))
    except Exception:print(json.dumps(dict(ok=False,failure='TAKEOVER_BOUND_STATE_OR_AUTHORIZATION_REJECTED')))
