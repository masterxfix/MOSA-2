"""One existing read-only connection; no migration executor and no writer credentials."""
import base64
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import current_preview_remote as reader, collector_migration5 as migration
from scripts import current_reconcile_remote as historical
from scripts.market_current import reconcile

def execute(env,paramiko):
    if env.get('GITHUB_RUN_ATTEMPT')!='1':return dict(status='FIRST_ATTEMPT_ONLY',business_writes=0)
    try:original=historical.original_plan(env)
    except Exception:original=None
    def consume(snapshot,preview):
        data=migration.unpack(snapshot['migration5']);state=migration.assess(data)
        if str(data['properties']['port'])!='3307':return dict(status='READ_IDENTITY_REJECTED',business_writes=0,execution_authorized=False)
        current=reconcile.public_summary(reconcile.compare(original,snapshot)) if original is not None else dict(classification='D',reason='ORIGINAL_PROTECTED_BASELINE_UNAVAILABLE')
        result=dict(status='READONLY_MIGRATION5_PREFLIGHT_COMPLETE',schema=state['status'],read_only_confirmed=True,
                    business_writes=0,provider_requests=0,current=current,execution_authorized=False,
                    mysql_version=data['properties']['version'],metadata_visibility='SELECT_ACCOUNT_SCOPE_ONLY')
        if state['status']=='SCHEMA4_READY':
            binding=migration.current_binding(snapshot)
            proof=dict(current,baseline_sha256=migration.digest(binding),baseline=binding,
                       historical_plan_sha256=env['RECONCILE_PLAN_SHA256'],historical_plan_run=env['TAKEOVER_PLAN_SOURCE_RUN'])
            plan=migration.prepare(data,env['GITHUB_SHA'],'migration5-prepare-'+env['GITHUB_RUN_ID'],proof)
            if current.get('classification')!='A':plan['blockers'].append('FIVE_CURRENT_TARGET_BASELINE_NOT_CONFIRMED')
            # Reuse the existing authenticated encrypted evidence envelope, no new secret/key.
            reader.profile.persist_backup({}, {'migration5-plan.json':base64.b64encode(json.dumps(plan,ensure_ascii=False).encode()).decode()},env['MOSA_TEST_SFTP_PASSWORD'])
            folder=Path(env['RUNNER_TEMP']);(folder/'mosa2-web-backup.sealed.json').rename(folder/'migration5-plan.sealed.json')
            result.update(plan_sha256=migration.digest(plan),plan_run_id=plan['run_id'],blockers=plan['blockers'])
        return result
    return reader.execute(env,paramiko,consume,bundle_script=migration.ROOT/'scripts/collector_migration5_bundle.php')

if __name__=='__main__':
    try:
        import paramiko
        result=execute(os.environ,paramiko);print(json.dumps(result,ensure_ascii=False))
        sys.exit(0 if result.get('status')=='READONLY_MIGRATION5_PREFLIGHT_COMPLETE' else 1)
    except Exception:
        print('{"status":"MIGRATION5_PREPARE_FAILED","business_writes":0,"execution_authorized":false}');sys.exit(1)
