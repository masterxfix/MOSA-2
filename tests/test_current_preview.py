"""Synthetic only. No provider, database connection, install or Current mutation."""
import copy
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch
from contextlib import contextmanager

from scripts.market_current import planner, preview
import test_market_current as fixtures
from test_observation_v2_writer_phase3 import row, route, CREATED

ROOT = Path(__file__).resolve().parents[1]


class CurrentPreviewTests(unittest.TestCase):
    def setUp(self):
        self.builder = fixtures.CurrentTests();self.builder.setUp()
        self.data = copy.deepcopy(self.builder.data)
        self.data['route']['external_key'] = 'synthetic'
        self.data['approval']['route_sha256'] = planner.route_hash(self.data['route'])

    def previous(self):
        self.data['current'] = planner.plan(self.data)['values']
        self.data['current_fact'] = self.data['facts'][0]

    def check(self, decision):
        original = copy.deepcopy(self.data)
        report = preview.preview(self.data)
        self.assertEqual(report['decision'], decision, report)
        self.assertEqual(self.data, original)
        self.assertEqual(report['business_writes'], 0)
        return report

    def test_current_missing_and_projection_is_existing_exact_plan(self):
        report = self.check('INSERT')
        self.assertEqual(report['candidate_projection'], planner.plan(self.data)['values'])
        self.assertIsNone(report['previous_current'])
        self.assertIn('SEPARATE_EXPLICIT_CURRENT_APPLY_ORDER',report['required_approvals'])

    def test_newer_market_quote(self):
        self.previous();self.data['now']='2026-01-01 00:00:15.000000'
        self.data['facts']=[self.builder.fact(row(market_at='2026-01-01 00:00:10',observed_at='2026-01-01 00:00:11',price='130'),'402')]
        self.assertEqual(self.check('UPDATE')['latest_observation']['age_seconds'],5)

    def test_already_current_and_identical_values(self):
        self.previous();report=self.check('UNCHANGED')
        self.assertEqual(report['previous_current']['price'],report['latest_observation']['price'])
        self.assertIsNone(report['candidate_projection'])

    def test_same_price_new_time_updates_provenance(self):
        self.previous();self.data['now']='2026-01-01 00:00:15.000000'
        self.data['facts']=[self.builder.fact(row(market_at='2026-01-01 00:00:10',observed_at='2026-01-01 00:00:11'),'402')]
        self.assertEqual(self.check('UPDATE')['candidate_projection']['observation_id'],'402')

    def test_old_market_new_acquisition_neither_replaces_nor_freshens(self):
        self.previous();self.data['now']='2026-01-01 01:00:00.000000'
        self.data['facts']=[self.builder.fact(row(market_at='2025-12-31 23:59:59',observed_at='2026-01-01 00:59:59'),'402')]
        report=self.check('UNCHANGED_OLDER')
        self.assertEqual(report['latest_observation']['age_seconds'],3601)
        self.assertEqual(report['previous_current']['age_seconds'],3600)

    def test_same_market_later_acquisition(self):
        self.previous();self.data['facts']=[self.builder.fact(row(observed_at='2026-01-01 00:00:03'),'402')]
        self.assertEqual(self.check('UPDATE')['latest_observation']['age_seconds'],5)

    def test_conflicting_observations_block(self):
        self.data['facts'].append(self.builder.fact(row(price='999'),'402'))
        report=self.check('BLOCKED');self.assertIsNone(report['candidate_projection'])
        self.assertEqual(report['reason'],'OBSERVATION_TIME_CONFLICT')

    def test_damaged_current_provenance_blocks_even_valid_candidate(self):
        self.previous();self.data['current']['observation_id']='999'
        report=self.check('BLOCKED')
        self.assertEqual(report['reason'],'CURRENT_PROVENANCE_INVALID')
        self.assertFalse(report['previous_current']['verified'])
        self.assertTrue(report['latest_observation']['verified'])

    def test_disabled_without_approval_is_not_approved(self):
        self.data['approval']=None
        report=self.check('BLOCKED')
        self.assertEqual(report['candidate_decision'],'INSERT')
        self.assertIn('EXPLICIT_DISABLED_ROUTE_PROJECTION_PERMISSION',report['required_approvals'])

    def test_enabled_route_still_requires_exact_approval_and_drift_blocks(self):
        self.data['route']['enabled']='1'
        self.check('BLOCKED')
        self.data['approval']['route_sha256']=planner.route_hash(self.data['route'])
        self.check('INSERT')

    def test_wrong_units_and_invalid_timestamps(self):
        for key,value in [('quote_unit_key','GBP'),('market_at','invalid'),('dedupe_key','00'*32),('source_id','999')]:
            data=copy.deepcopy(self.data);data['facts'][0][key]=value
            with self.subTest(key=key):self.assertEqual(preview.preview(data)['decision'],'BLOCKED')

    def test_missing_and_no_candidate_with_current(self):
        data=copy.deepcopy(self.data);data['facts']=[]
        self.assertEqual(preview.preview(data)['decision'],'MISSING')
        self.previous();self.data['facts']=[];self.check('UNCHANGED')

    def snapshot(self):
        p=subprocess.run(['php',str(ROOT/'tests/fixtures/current_preview.php'),str(ROOT)],
            input=json.dumps(dict(action='scope')),text=True,capture_output=True,check=True)
        self.assertEqual(p.stderr,'');scopes=json.loads(p.stdout);entries=[]
        for i,(isin,scope) in enumerate(scopes.items()):
            raw=row(asset_id=str(1100+i),route_id=str(7100+i))
            physical=route(raw)['route']|dict(route_type='quote',priority='0',enabled='0',external_key=scope['external_key'])
            scope.update(asset_id=raw['asset_id'],route_id=raw['route_id'])
            data=dict(route=physical,approval=None,now=CREATED,facts=[self.builder.fact(raw,str(9000+i))],current=None,current_fact=None)
            entries.append(dict(isin=isin,name=preview.php(dict(operation='scope'),ROOT/'scripts/market_current/preview_read.php')['scope'][isin],scope_rows=[scope],input=data))
        return entries

    def test_five_scope_ids_resolved_from_rows_bounded_readonly_and_no_mutation(self):
        entries=self.snapshot()
        p=subprocess.run(['php',str(ROOT/'tests/fixtures/current_preview.php'),str(ROOT)],
            input=json.dumps(dict(action='gather',items=entries,now=CREATED)),capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'');reply=json.loads(p.stdout)
        self.assertTrue(reply['unchanged']);self.assertEqual(reply['events'],['SET TRANSACTION READ ONLY','BEGIN','ROLLBACK'])
        self.assertEqual(len(reply['calls']),25)
        report=preview.snapshot_preview(reply['snapshot'])
        self.assertEqual([x['decision'] for x in report['reports']],['BLOCKED']*5)
        self.assertTrue(all(x['candidate_decision']=='INSERT' for x in report['reports']))
        self.assertTrue(all(x['input']['approval'] is None for x in reply['snapshot']['items']))
        public=json.dumps(preview.public_summary(report))
        for private in ('123.4500000000','7100','1100','observation_id','route_sha256','market_at'):
            self.assertNotIn(private,public)
        bad=copy.deepcopy(reply['snapshot']);bad['items'][0]['scope_rows'][0]['source_enabled']='0'
        self.assertEqual(preview.snapshot_preview(bad)['reports'][0]['reason'],'QUALIFIED_REFERENCE_REJECTED')
        # Exercise the existing Current origin lookup as well, bounded to this asset.
        entries[0]['input']['current']=planner.plan_facts(entries[0]['input'])['values']
        entries[0]['input']['current_fact']=entries[0]['input']['facts'][0]
        p=subprocess.run(['php',str(ROOT/'tests/fixtures/current_preview.php'),str(ROOT)],
            input=json.dumps(dict(action='gather',items=entries,now=CREATED)),capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'');with_current=json.loads(p.stdout)
        self.assertTrue(with_current['unchanged']);self.assertEqual(len(with_current['calls']),26)
        origins=[q for q in with_current['calls'] if 'WHERE id=? AND asset_id=?' in q['sql']]
        self.assertEqual(origins[0]['params'],['9000','1100'])
        self.assertEqual(preview.snapshot_preview(with_current['snapshot'])['reports'][0]['decision'],'UNCHANGED')

    def test_bundle_uses_original_reader_and_rejects_write_grants(self):
        p=subprocess.run(['php',str(ROOT/'scripts/market_current/read_bundle.php')],capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'')
        lint=subprocess.run(['php','-l'],input='<?php\n'+p.stdout,capture_output=True,text=True)
        self.assertEqual(lint.returncode,0,lint.stderr+lint.stdout)
        for required in ('function inputs(', 'function grants(', 'function scopeSql(', 'SET SESSION TRANSACTION READ ONLY',"'h29077_mosa2_read'"):
            self.assertIn(required,p.stdout)
        for forbidden in ('MOSA_TEST_DB_PASSWORD','function refresh(', 'function run(', 'file_put_contents','INSERT INTO','UPDATE m2_','DELETE FROM'):
            self.assertNotIn(forbidden,p.stdout)
        # Existing tested SELECT-only grant validator remains the live admission guard.
        code=r'''require $argv[1];try{\Mosa2\MarketReadAccess\grants([['GRANT SELECT, INSERT ON `h29077_mosa2_test`.* TO x']],true);exit(9);}catch(Throwable){echo 'BLOCKED';}'''
        r=subprocess.run(['php','-r',code,str(ROOT/'scripts/market_current/read_access.php')],capture_output=True,text=True,check=True)
        self.assertEqual(r.stdout,'BLOCKED')

    def test_live_attempt_guard_does_not_touch_ssh_or_database(self):
        from scripts import current_preview_remote as remote
        with patch.object(remote.access,'ssh_client') as connect:
            report=remote.execute(dict(GITHUB_RUN_ATTEMPT='2'),Mock())
        connect.assert_not_called();self.assertFalse(report['real_data_checked'])

    def test_missing_reader_stops_after_one_fileless_inspection(self):
        from scripts import current_preview_remote as runner
        @contextmanager
        def ssh(*args):yield Mock()
        with patch.object(runner.profile,'configuration',return_value={}),patch.object(runner.access,'ssh_client',ssh),\
             patch.object(runner.remote,'capability',return_value=('php',[])),\
             patch.object(runner.remote,'remote_call',return_value=(0,b'{"ok":false,"failure":"READ_CONFIG_UNAVAILABLE"}',False,1)) as call:
            report=runner.execute(dict(GITHUB_RUN_ATTEMPT='1'),Mock())
        self.assertEqual(call.call_count,1)
        self.assertEqual(report['failure'],'READ_CONFIG_UNAVAILABLE');self.assertFalse(report['real_data_checked'])
        self.assertNotIn('password',json.dumps(report))

    def guard(self, fault=''):
        if not hasattr(self, '_guard_entries'):self._guard_entries=self.snapshot()
        p=subprocess.run(['php','-d','display_errors=stderr',str(ROOT/'tests/fixtures/current_preview.php'),str(ROOT)],
            input=json.dumps(dict(action='guard',items=self._guard_entries,fault=fault)),text=True,capture_output=True,check=True)
        self.assertEqual(p.stderr,'')
        return json.loads(p.stdout)

    def test_session_scope_proof_fixes_legacy_default_and_reads_without_mutation(self):
        result=self.guard();reply=result['reply']
        self.assertTrue(reply['ok']);self.assertTrue(reply['read_only_confirmed'])
        self.assertIn('LEGACY_SESSION_DEFAULT_READ_WRITE',reply['diagnostics'])
        self.assertIn('TRANSACTION_READ_ONLY_VARIABLE_SUPPORTED',reply['diagnostics'])
        self.assertEqual(result['events'],['SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ',
            'SET SESSION TRANSACTION READ ONLY','BEGIN','ROLLBACK'])
        self.assertEqual(len(result['calls']),25);self.assertTrue(result['unchanged']);self.assertFalse(result['active'])
        self.assertEqual(len([q for q in result['queries'] if q.startswith('SELECT @@session.transaction_read_only')]),2)

    def test_invalid_guard_states_abort_before_any_business_read(self):
        for fault,code in [('identity','READ_IDENTITY_REJECTED'),('active','READ_IDENTITY_REJECTED'),
                ('engine','READ_DATABASE_PROPERTIES_REJECTED'),('unsupported','READ_TRANSACTION_VARIABLE_UNSUPPORTED'),
                ('privileges','READ_PRIVILEGES_REJECTED'),('missing_select','READ_PRIVILEGES_REJECTED'),('setup','READ_SESSION_SETUP_REJECTED'),
                ('session','READ_SESSION_STATE_REJECTED'),('begin','READ_TRANSACTION_START_REJECTED'),
                ('isolation','READ_SESSION_STATE_REJECTED'),('transaction','READ_TRANSACTION_STATE_REJECTED'),
                ('snapshot','READ_SNAPSHOT_DATA_REJECTED')]:
            with self.subTest(fault=fault):
                result=self.guard(fault)
                self.assertEqual(result['reply']['failure'],code);self.assertFalse(result['reply']['ok'])
                self.assertEqual(result['calls'],[]);self.assertTrue(result['unchanged']);self.assertFalse(result['active'])
                for private in ('SQL private','password','secret','123.45'):self.assertNotIn(private,json.dumps(result['reply']))

    def test_failed_rollback_invalidates_success(self):
        result=self.guard('rollback')
        self.assertFalse(result['reply']['ok']);self.assertEqual(result['reply']['failure'],'READ_ROLLBACK_REJECTED')
        self.assertNotIn('snapshot',result['reply']);self.assertTrue(result['unchanged'])

    def test_missing_and_invalid_remote_snapshots_never_pass(self):
        from scripts import current_preview_remote as runner
        @contextmanager
        def ssh(*args):yield Mock()
        replies=[dict(ok=True),dict(ok=True,read_only_confirmed=True),
            dict(ok=True,read_only_confirmed=True,snapshot={}),
            dict(ok=True,read_only_confirmed=True,snapshot=dict(items=[],as_of=CREATED)),
            dict(ok=False,failure='SQL password private',diagnostics=['private-secret']),
            dict(ok=False,failure='READ_TRANSACTION_STATE_REJECTED')]
        for reply in replies:
            with self.subTest(reply=reply),patch.object(runner.profile,'configuration',return_value={}),\
                 patch.object(runner.access,'ssh_client',ssh),patch.object(runner.remote,'capability',return_value=('php',[])),\
                 patch.object(runner.remote,'remote_call',return_value=(0,json.dumps(reply).encode(),False,1)) as call:
                report=runner.execute(dict(GITHUB_RUN_ATTEMPT='1'),Mock())
                self.assertFalse(report['real_data_checked']);self.assertEqual(call.call_count,1)
                for private in ('password','private-secret','SQL'):self.assertNotIn(private,json.dumps(report))

    def test_remote_verified_snapshot_publishes_only_statuses(self):
        from scripts import current_preview_remote as runner
        @contextmanager
        def ssh(*args):yield Mock()
        reply=dict(ok=True,read_only_confirmed=True,snapshot=dict(items=self.snapshot(),as_of=CREATED),
            diagnostics=['MYSQL_80_PROPERTIES_CONFIRMED','private-secret'])
        with patch.object(runner.profile,'configuration',return_value={}),patch.object(runner.access,'ssh_client',ssh),\
             patch.object(runner.remote,'capability',return_value=('php',[])),\
             patch.object(runner.remote,'remote_call',return_value=(0,json.dumps(reply).encode(),False,1)) as call:
            report=runner.execute(dict(GITHUB_RUN_ATTEMPT='1'),Mock())
        self.assertEqual(call.call_count,1);self.assertTrue(report['real_data_checked']);self.assertTrue(report['read_only_confirmed'])
        self.assertEqual(report['diagnostics'],['MYSQL_80_PROPERTIES_CONFIRMED'])
        self.assertEqual([item['decision'] for item in report['reports']],['BLOCKED']*5)
        self.assertTrue(all(item['current_status']=='CURRENT_MISSING' and item['candidate_decision']=='INSERT' for item in report['reports']))
        for private in ('private-secret','123.4500000000','observation_id','route_sha256','market_at'):
            self.assertNotIn(private,json.dumps(report))


if __name__=='__main__':unittest.main()
