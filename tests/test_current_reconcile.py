"""Synthetic original/target/mixed/unknown comparisons; no DB/provider calls."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch
from scripts.market_current import reconcile, planner, takeover
import test_current_takeover as fixtures
from scripts import current_reconcile_remote as runner
ROOT=Path(__file__).resolve().parents[1]

class CurrentReconcileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.CurrentTakeoverTests.setUpClass()
        cls.plan=copy.deepcopy(fixtures.CurrentTakeoverTests.plan)
        cls.snapshot=copy.deepcopy(fixtures.CurrentTakeoverTests.snapshot)
        cls.snapshot['as_of']='2026-01-01 00:02:00.000000'
        for entry in cls.snapshot['items']:entry['input']['now']=cls.snapshot['as_of']

    def target(self,count=5):
        snapshot=copy.deepcopy(self.snapshot)
        for entry,item in zip(snapshot['items'][:count],self.plan['items'][:count]):
            data=entry['input'];at='2026-01-01 00:01:00.000000'
            data['current']=planner.plan_facts(dict(data,now=at))['values']
            data['current_fact']=next(f for f in data['facts'] if f['id']==item['observation_id'])
        return snapshot

    def test_b_original_five_exact_rows_and_absences(self):
        before=copy.deepcopy(self.snapshot);plan=copy.deepcopy(self.plan)
        report=reconcile.compare(self.plan,self.snapshot)
        self.assertEqual(report['classification'],'B')
        self.assertEqual([x['state'] for x in report['reports']],['ORIGINAL']*5)
        self.assertEqual([x['current_status'] for x in report['reports']],['PRESENT']*2+['MISSING']*3)
        self.assertEqual(self.snapshot,before);self.assertEqual(self.plan,plan)

    def test_a_target_uses_exact_native_values_and_actual_projection_timestamp(self):
        report=reconcile.compare(self.plan,self.target())
        self.assertEqual(report['classification'],'A')
        self.assertTrue(all(x['provenance']=='VALID' and x['state']=='TARGET' for x in report['reports']))

    def test_c_mixed_original_and_target(self):
        report=reconcile.compare(self.plan,self.target(2))
        self.assertEqual(report['classification'],'C')
        self.assertEqual([x['state'] for x in report['reports']],['TARGET']*2+['ORIGINAL']*3)

    def test_d_corrupt_provenance_or_read_failure(self):
        snapshot=self.target();snapshot['items'][0]['input']['current']['observation_dedupe_key']='0'*64
        self.assertEqual(reconcile.compare(self.plan,snapshot)['classification'],'D')
        snapshot=copy.deepcopy(self.snapshot);snapshot['items'][0]['input']=None;snapshot['items'][0]['blocked_reason']='READ_SCOPE_OR_INPUT_REJECTED'
        self.assertEqual(reconcile.compare(self.plan,snapshot)['classification'],'D')

    def test_route_and_scoped_metadata_drift_cannot_claim_a_or_b(self):
        snapshot=copy.deepcopy(self.snapshot);snapshot['items'][0]['input']['route']['external_key']='wrong'
        self.assertEqual(reconcile.compare(self.plan,snapshot)['classification'],'D')
        snapshot=copy.deepcopy(self.snapshot);snapshot['items'][0]['input']['route']['updated_at']='2026-01-01 00:01:00.000000'
        report=reconcile.compare(self.plan,snapshot)
        self.assertEqual(report['classification'],'C');self.assertEqual(report['reports'][0]['routes'],'CHANGED')

    def test_wrong_current_values_and_forged_target_timestamp_fail(self):
        snapshot=self.target();snapshot['items'][0]['input']['current']['price']='9.0000000000'
        self.assertEqual(reconcile.compare(self.plan,snapshot)['classification'],'D')
        snapshot=self.target();snapshot['items'][0]['input']['current']['updated_at']='2027-01-01 00:00:00.000000'
        self.assertEqual(reconcile.compare(self.plan,snapshot)['classification'],'C')

    def test_fixed_scope_and_duplicate_guard(self):
        for entries in (self.snapshot['items'][:4],self.snapshot['items'][:4]+self.snapshot['items'][:1]):
            with self.assertRaises(ValueError):reconcile.compare(self.plan,dict(self.snapshot,items=entries))

    def test_public_summary_never_exports_private_values_or_full_table_guarantee(self):
        report=reconcile.compare(self.plan,self.target());public=reconcile.public_summary(report)
        text=json.dumps(public)
        for value in ('123.4500000000','observation_id','scope_rows','market_at','asset_id','private_current'):
            self.assertNotIn(value,text)
        self.assertEqual(public['other_tables'],'NOT_VERIFIABLE_NO_COMPLETE_BASELINE')
        self.assertEqual(public['business_writes'],0)

    def test_expired_plan_is_evidence_never_reauthorized(self):
        env=dict(RECONCILE_SOURCE_COMMIT=self.plan['revision'],RECONCILE_PLAN_SHA256=takeover.digest(self.plan),TAKEOVER_PLAN_SOURCE_RUN='12345')
        with patch.object(runner.artifacts,'artifact_plan',return_value=self.plan) as load:
            result=runner.original_plan(env)
        self.assertIsNone(result['authorization']);self.assertEqual(load.call_args.args[0]['GITHUB_SHA'],self.plan['revision'])
        with patch.object(runner.artifacts,'artifact_plan',return_value=self.plan),self.assertRaises(ValueError):
            runner.original_plan(dict(env,RECONCILE_PLAN_SHA256='0'*64))

    def test_artifact_failure_stops_before_db_and_only_one_read_call(self):
        with patch.object(runner,'original_plan',side_effect=ValueError),patch.object(runner.reader,'execute') as read:
            result=runner.execute(dict(GITHUB_RUN_ATTEMPT='1'),Mock())
        read.assert_not_called();self.assertEqual(result['status'],'RECONCILE_ORIGINAL_ARTIFACT_REJECTED')
        with patch.object(runner,'original_plan',return_value=self.plan),patch.object(runner.reader,'execute',return_value={'status':'TEST'}) as read:
            runner.execute(dict(GITHUB_RUN_ATTEMPT='1'),Mock())
        self.assertEqual(read.call_count,1)
        with patch.object(runner.reader,'execute') as read:
            runner.execute(dict(GITHUB_RUN_ATTEMPT='2'),Mock())
        read.assert_not_called()

    def test_150_second_timeout_is_possible_but_generic_failure_cannot_prove_it(self):
        from scripts import current_takeover_remote as failed
        for error in (subprocess.TimeoutExpired('private',150),ValueError('different cause')):
            with patch.object(failed.subprocess,'run',side_effect=error),self.assertRaises(Exception):failed.php({})
        self.assertIn('except Exception:',(ROOT/'scripts/current_takeover_remote.py').read_text())
        self.assertIn("timeout=150",(ROOT/'scripts/current_takeover_remote.py').read_text())

    def test_reconcile_workflow_has_no_writer_secret_or_apply_call(self):
        workflow=(ROOT/'.github/workflows/observation-view-check.yml').read_text()
        block=workflow[workflow.index('      - name: One READ ONLY comparison'):]
        self.assertNotIn('MOSA_TEST_DB_PASSWORD',block)
        code=(ROOT/'scripts/current_reconcile_remote.py').read_text()
        for forbidden in ('writer_call(','.apply(','.approvals(','no_previous_claim(','takeover.prepare('):self.assertNotIn(forbidden,code)

if __name__=='__main__':unittest.main()
