"""Synthetic stored-fact selection, provenance and explicit approval contracts."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from scripts.market_current import planner as current
from test_observation_v2_writer_phase3 import row, route, CREATED

ROOT=Path(__file__).resolve().parents[1]

class CurrentTests(unittest.TestCase):
    def setUp(self):
        raw=row(); self.route=route(raw)['route']|dict(route_type='quote',priority='0',enabled='0')
        self.data=dict(route=self.route,approval=dict(route_sha256=current.route_hash(self.route),approved_at=CREATED,allow_disabled_projection=True),now=CREATED,facts=[self.fact(raw)])

    def fact(self,raw,identity='401'):
        binding=route(raw);p=current.writer.WriterPlanner(current.writer.observation.catalog_module.normative_catalog(),[binding]).plan(raw,format_version=2,intent='NEW_NATIVE_V2',created_at=CREATED)
        self.assertEqual(p['decision'],'INSERT',p)
        return p['normalized']|dict(id=identity,observation_format_version='2',dedupe_key=p['dedupe_key'].hex().upper(),created_at=CREATED)

    def previous(self):
        self.data['current']=current.plan(self.data)['values'];self.data['current_fact']=self.data['facts'][0]

    def test_insert_preserves_native_exact_fact_and_no_daily_invention(self):
        p=current.plan(self.data);self.assertEqual(p['decision'],'INSERT');v=p['values']
        self.assertEqual(v['price'],'123.4500000000');self.assertEqual(v['observation_id'],'401')
        for k in current.UNITS[:6]:self.assertEqual(v[k],self.data['facts'][0][k])
        for k in ('day_open','day_high','day_low','previous_close','day_volume','day_volume_unit_key'):self.assertIsNone(v[k])

    def test_repetition_does_not_touch_update_timestamp(self):
        self.previous();self.data['now']='2026-01-02 00:00:00.000000';p=current.plan(self.data)
        self.assertEqual(p['decision'],'UNCHANGED');self.assertEqual(p['values'],self.data['current'])

    def test_old_market_time_cannot_win_with_newer_observed_time(self):
        self.previous();self.data['facts']=[self.fact(row(market_at='2025-12-31 23:59:00',observed_at='2026-01-01 00:00:03'),'402')]
        self.assertEqual(current.plan(self.data)['decision'],'UNCHANGED_OLDER')

    def test_newer_observation_at_same_market_time_wins(self):
        self.previous();self.data['facts']=[self.fact(row(observed_at='2026-01-01 00:00:03',price='125'),'402')]
        p=current.plan(self.data);self.assertEqual(p['decision'],'UPDATE');self.assertEqual(p['values']['observation_id'],'402')

    def test_equal_time_disagreement_has_no_id_tiebreaker(self):
        self.data['facts'].append(self.fact(row(price='125'),'402'))
        for facts in (self.data['facts'],self.data['facts'][::-1]):
            with self.assertRaisesRegex(ValueError,'equal_time_conflict'):current.plan(self.data|dict(facts=facts))

    def test_equal_time_disagreement_with_current_rejected(self):
        self.previous();self.data['facts']=[self.fact(row(price='125'),'402')]
        with self.assertRaisesRegex(ValueError,'equal_time_conflict'):current.plan(self.data)

    def test_stored_key_and_unit_drift_rejected(self):
        for field,value in [('dedupe_key','00'*32),('quote_unit_key','GBP'),('observation_format_version',None)]:
            data=copy.deepcopy(self.data);data['facts'][0][field]=value
            with self.assertRaises(ValueError):current.plan(data)

    def test_route_disabled_requires_explicit_separate_approval(self):
        self.data['approval'].pop('allow_disabled_projection')
        with self.assertRaisesRegex(ValueError,'not_approved'):current.plan(self.data)

    def test_approval_pins_complete_physical_route(self):
        self.data['route']['enabled']='1'
        with self.assertRaisesRegex(ValueError,'approval_drift'):current.plan(self.data)

    def test_current_drift_and_missing_origin_rejected(self):
        self.previous();self.data['current']['price']='999.0000000000'
        with self.assertRaisesRegex(ValueError,'projection_drift'):current.plan(self.data)
        self.data['current_fact']=None
        with self.assertRaisesRegex(ValueError,'origin_missing'):current.plan(self.data)

    def test_bounded_missing_and_unchanged_when_no_candidates(self):
        self.assertEqual(current.plan(self.data|dict(facts=[]))['decision'],'MISSING')
        self.previous();self.data['facts']=[];self.assertEqual(current.plan(self.data)['decision'],'UNCHANGED')
        with self.assertRaisesRegex(ValueError,'bounded'):current.plan(self.data|dict(facts=[self.data['current_fact']]*3))

    def test_gbx_native_unit_is_not_converted_to_gbp(self):
        fact=self.fact(row('GBX'));r=route(row('GBX'))['route']|dict(route_type='quote',priority='0',enabled='0')
        self.data.update(route=r,facts=[fact]);self.data['approval']['route_sha256']=current.route_hash(r)
        v=current.plan(self.data)['values'];self.assertEqual((v['price'],v['quote_unit_key'],v['currency']),('123.4500000000','GBX','GBP'))

    @unittest.skipUnless(shutil.which('php'),'PHP required')
    def test_php_read_model_market_age_not_acquisition_age_and_exact_price(self):
        code=r'''require $argv[1]; $row=['display_name'=>'Synthetic','source_name'=>'Source','venue'=>'Venue','price'=>'123456789012345678.1234567890','valid_binding'=>'1','quote_unit_key'=>'GBX','quote_unit_version'=>'1','currency'=>'GBP','quantity_basis_unit_key'=>null,'quantity_basis_amount'=>null,'market_at'=>'2026-01-01 00:00:00.000000','observed_at'=>'2026-01-01 00:59:59.000000'];echo json_encode(\Mosa2\MarketRead\present($row,'2026-01-01 01:00:00.000000',1800));'''
        p=subprocess.run(['php','-r',code,str(ROOT/'api/read_model.php')],capture_output=True,text=True,check=True)
        v=json.loads(p.stdout);self.assertEqual(v['status'],'stale');self.assertEqual(v['price'],'123456789012345678.1234567890');self.assertEqual(v['unit'],'GBX')

    def test_public_path_has_no_provider_or_mutation_capability(self):
        code=(ROOT/'api/read_model.php').read_text();endpoint=(ROOT/'api/market.php').read_text()
        reader=(ROOT/'api/current_read.php').read_text()
        scope=(ROOT/'api/qualified_scope.php').read_text()
        self.assertIn('readTransaction($p,',reader)
        self.assertIn('SET SESSION TRANSACTION READ ONLY',scope)
        self.assertIn('SELECT @@session.transaction_read_only',scope)
        self.assertIn('$p->rollBack()',scope);self.assertIn('LIMIT 1',reader)
        code+=reader+scope
        for verb in ('INSERT ','UPDATE ','DELETE ','REPLACE ','ALTER ','TRUNCATE '):self.assertNotIn(verb,code+endpoint)
        self.assertNotIn('market_collector',code+endpoint);self.assertNotIn('m2_market_observations',code)
        self.assertIn("dirname(__DIR__,2).'/mosa2-market-read-private/access.php'",endpoint)

    def test_existing_bridge_duplicate_is_opt_in_and_uses_same_writer(self):
        from dataclasses import asdict
        from scripts.market_collector import live_bridge as bridge
        from test_market_collector_v1 import FrankfurtCollectorTests
        fixture=FrankfurtCollectorTests();fixture.setUp();first=fixture.run_pipeline()['writer_plan']
        request=dict(action='plan',acquired=dict(adapter_module='scripts.market_collector.boerse_frankfurt',adapter_class='FrankfurtSnapshotV1',provider_key=fixture.adapter.provider_key,request_key=fixture.request.request_key,requested_at=fixture.request.requested_at,instrument=fixture.request.instrument,response=bridge.transport(asdict(fixture.response))),route=dict(fixture.route.route),created_at=fixture.created,
                     existing=bridge.transport([dict(format_version=2,payload=first['normalized'],dedupe_key=first['dedupe_key'])]))
        with self.assertRaisesRegex(ValueError,'writer decision'):bridge.run(request)
        result=bridge.run(request|dict(allow_duplicate=True));self.assertEqual(result['plan']['decision'],'DUPLICATE_UNCHANGED')
        self.assertEqual(bridge.restore(result['plan'])['dedupe_key'],first['dedupe_key'])

    @unittest.skipUnless(shutil.which('php'),'PHP required')
    def test_actual_read_path_prepares_bounded_select_rolls_back_and_rejects_write_grants(self):
        p=subprocess.run(['php',str(ROOT/'tests/fixtures/market_read_contract.php'),str(ROOT)],capture_output=True,text=True,check=True)
        r=json.loads(p.stdout);self.assertEqual(r['events'],['SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ','SET SESSION TRANSACTION READ ONLY','BEGIN','ROLLBACK'])
        self.assertEqual(len(r['parameters']),11);self.assertEqual(len(r['sql']),4)
        self.assertTrue(any('LIMIT 1' in q for q in r['sql']));self.assertEqual(r['unsafe_grants_rejected'],[True]*5)
        self.assertEqual([x['price'] for x in r['result']['items']],['2.0000000000']*5)

    @unittest.skipUnless(shutil.which('php'),'PHP required')
    def test_reader_provisioning_before_migration_does_not_query_future_columns(self):
        p=subprocess.run(['php',str(ROOT/'tests/fixtures/market_read_contract.php'),str(ROOT)],capture_output=True,text=True,check=True)
        r=json.loads(p.stdout)['provision'];self.assertEqual(r['probe'],dict(stage='SCHEMA3_EMPTY_CURRENT_PREFLIGHT',item_count=2))
        self.assertEqual(r['events'],['SET TRANSACTION READ ONLY','BEGIN','ROLLBACK']);self.assertEqual(len(r['sql']),3)
        self.assertNotIn('observation_id',' '.join(r['sql']));self.assertIn('LIMIT 1',r['sql'][-1])

    @unittest.skipUnless(shutil.which('php'),'PHP required')
    def test_current_scope_uses_physical_id_from_actual_existing_route_plan(self):
        from test_market_onboarding import MarketOnboardingTests
        state, manifest = MarketOnboardingTests().existing_live()
        code=r'''require $argv[1];$in=json_decode(stream_get_contents(STDIN),true);try{\Mosa2\MarketCurrent\approvalScope($in['state'],[['manifest'=>$in['manifest']]],$in['approvals']);echo 'PASS';}catch(Throwable $e){echo $e->getMessage();}'''
        for identity, expected in [('11','PASS'), ('12','current_batch_approval_scope')]:
            p=subprocess.run(['php','-r',code,str(ROOT/'scripts/market_current/refresh.php')],
                input=json.dumps(dict(state=state,manifest=manifest,approvals=[dict(route_id=identity)])),capture_output=True,text=True,check=True)
            self.assertEqual(p.stdout,expected);self.assertEqual(p.stderr,'')

    @unittest.skipUnless(shutil.which('php'),'PHP required')
    def test_version_four_metadata_extends_exact_existing_schema_and_parses_check(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            for n,name in [(1,'0001_core_asset_identity.sql'),(2,'0002_market_current_history.sql'),(3,'0003_market_units.sql')]:
                (Path(folder)/f'{n:04}.sql').write_bytes((ROOT/'docs/database/migrations'/name).read_bytes())
            code=r'''require $argv[1];$s=\Mosa2\MarketCurrentMigration\schemas($argv[2]);$t=$s['m2_market_current'];(new \Mosa2\Phase2\CheckExpression($t['checks']['ck_market_current_provenance']))->parse();echo json_encode(['tables'=>count($s),'columns'=>array_slice($t['columns'],-4),'fk'=>$t['fks']['fk_market_current_observation']]);'''
            p=subprocess.run(['php','-r',code,str(ROOT/'scripts/market_current/migration.php'),folder],capture_output=True,text=True,check=True)
            r=json.loads(p.stdout);self.assertEqual(r['tables'],17);self.assertEqual(r['columns']['observation_id']['type'],'bigint unsigned');self.assertEqual(r['fk']['table'],'m2_market_observations')

if __name__=='__main__':unittest.main()
