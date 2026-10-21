"""One existing READ ONLY snapshot; the historical artifact supplies no execution authority."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import current_preview_remote as reader, current_takeover_remote as artifacts
from scripts.market_current import reconcile, takeover


def original_plan(env):
    # Reuse encrypted artifact retrieval and existing SSH-secret decryption. No local attachments.
    source_env = dict(env, GITHUB_SHA=env['RECONCILE_SOURCE_COMMIT'])
    plan = artifacts.artifact_plan(source_env)
    if takeover.digest(plan) != env['RECONCILE_PLAN_SHA256']:
        raise ValueError('historical plan digest')
    if plan['revision'] != env['RECONCILE_SOURCE_COMMIT'] or plan['run_id'] != 'current-once-' + env['TAKEOVER_PLAN_SOURCE_RUN']:
        raise ValueError('historical plan binding')
    return plan


def execute(env, paramiko):
    if env.get('GITHUB_RUN_ATTEMPT') != '1':
        return dict(status='RECONCILE_FIRST_ATTEMPT_ONLY', business_writes=0)
    try:
        plan = original_plan(env)  # Must pass before the only DB inspection.
    except Exception:
        return dict(status='RECONCILE_ORIGINAL_ARTIFACT_REJECTED', business_writes=0)
    def consume(snapshot, unused_preview):
        report = reconcile.compare(plan, snapshot)
        return dict(status='READONLY_RECONCILIATION_COMPLETE', **reconcile.public_summary(report))
    return reader.execute(env, paramiko, consume)


if __name__ == '__main__':
    try:
        import paramiko
        result = execute(os.environ, paramiko)
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result.get('status') == 'READONLY_RECONCILIATION_COMPLETE' else 1)
    except Exception:
        print(json.dumps(dict(status='READONLY_RECONCILIATION_FAILED', business_writes=0)))
        sys.exit(1)
