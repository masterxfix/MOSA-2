"""Execute the PHP runtime against transactional PDO doubles and the real v2 bridge/writer.

SQL shape/query-count evidence is offline; it is not MySQL timing or EXPLAIN evidence.
"""
import copy
import base64
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import test_market_onboarding as onboarding
import test_market_collector_v1 as collector_fixtures
from scripts.market_collector import live_bridge
from test_market_live_batch import isin

ROOT=Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state,cls.manifest=onboarding.MarketOnboardingTests().existing_live()
        fixture=collector_fixtures.FrankfurtCollectorTests();fixture.setUp()
        cls.acquired=dict(provider_requests=1,adapter_module='scripts.market_collector.boerse_frankfurt',adapter_class='FrankfurtSnapshotV1',
            provider_key=fixture.adapter.provider_key,request_key=fixture.request.request_key,requested_at=fixture.request.requested_at,
            instrument=fixture.request.instrument,response=live_bridge.transport(asdict(fixture.response)))
        cls.config=dict(python=sys.executable,project=str(ROOT),php='php',runtime_path=os.environ['PATH'])
        for field in ['identifier_value','normalized_value']:
            cls.manifest['identity'][field]=fixture.request.instrument
            cls.state['m2_asset_identifiers'][0][field]=fixture.request.instrument
        cls.manifest.update(instrument=fixture.request.instrument,adapter_module=cls.acquired['adapter_module'],adapter_class=cls.acquired['adapter_class'])
        cls.manifest['route_evidence']['row'].update(isin=fixture.request.instrument,provider_key=fixture.adapter.provider_key)
        cls.state['m2_sources'][0]['source_key']='provider:'+fixture.adapter.provider_key
        qualified=onboarding.route_input()|dict(evidence=cls.manifest['route_evidence'])
        cls.state['m2_asset_source_routes']=[onboarding.call(action='route',routes=[],qualified=qualified,units=onboarding.UNITS)['result']['row']|dict(id='11')]

    def call(self,**extra):
        data=dict(state=self.state,manifest=self.manifest,acquired=self.acquired,config=self.config)|extra
        p=subprocess.run(['php',str(ROOT/'tests/market_runtime_fixture.php')],input=json.dumps(data),text=True,capture_output=True,check=True)
        self.assertEqual(p.stderr,'');return json.loads(p.stdout)

    def test_insert_and_duplicate_use_exact_same_observation_and_readback(self):
        result=self.call(runs=2);first,second=result['reports']
        for report in (first,second):
            self.assertTrue(report['ok'],report);self.assertTrue(report['committed'])
            self.assertEqual(report['readback'],'PASS');self.assertEqual(report['replay'],'DUPLICATE_UNCHANGED')
        self.assertEqual([first['writer'],second['writer']],['INSERT','DUPLICATE_UNCHANGED'])
        self.assertEqual(first['observation_id'],second['observation_id'])
        self.assertEqual(len(result['state']['m2_market_observations']),1)
        self.assertEqual(result['providers'],2)
        for table,rows in self.state.items():
            if table not in ('m2_units','m2_market_observations'):self.assertEqual(result['state'][table],rows)
        self.assertEqual(result['state']['m2_market_current'],[]);self.assertEqual(result['state']['m2_market_bars'],[])

    def test_history_growth_does_not_increase_queries_or_returned_rows(self):
        small,large=self.call(history_size=0),self.call(history_size=20000)
        self.assertTrue(small['reports'][0]['ok'],small['reports']);self.assertTrue(large['reports'][0]['ok'],large['reports'])
        self.assertEqual(len(small['queries']),len(large['queries']))
        self.assertEqual(small['returned_rows'],large['returned_rows'])
        self.assertLessEqual(len(large['queries']),100)
        for sql in large['queries']:
            if 'FROM m2_market_observations' in sql:self.assertIn(' WHERE ',sql);self.assertIn(' LIMIT 2',sql)
            self.assertNotIn('SHOW COLUMNS',sql)
        self.assertEqual(len(large['state']['m2_market_observations']),20001)

    def test_runtime_writes_only_observations(self):
        result=self.call();writes=[s for s in result['queries'] if s.startswith(('INSERT ','UPDATE ','DELETE ','REPLACE ','ALTER '))]
        self.assertEqual(len(writes),1);self.assertTrue(writes[0].startswith('INSERT INTO m2_market_observations '))

    def test_existing_current_and_bars_are_untouched_without_reading_them(self):
        state=copy.deepcopy(self.state);state['m2_market_current']=[dict(asset_id='7',price='123')];state['m2_market_bars']=[dict(id='44',price='456')]
        result=self.call(state=state);self.assertTrue(result['reports'][0]['ok'],result['reports'])
        for table in ['m2_market_current','m2_market_bars']:
            self.assertEqual(result['state'][table],state[table]);self.assertFalse(any(table in sql for sql in result['queries']))

    def test_provider_and_drift_fail_before_commit(self):
        for fault in ['provider','drift','ledger_drift']:
            result=self.call(fault=fault);report=result['reports'][0]
            self.assertFalse(report['ok']);self.assertFalse(report['committed']);self.assertEqual(result['providers'],1)
            self.assertEqual(result['state']['m2_market_observations'],[])

    def test_failed_replay_rolls_back_insert_and_independently_proves_rollback(self):
        result=self.call(fault='replay');report=result['reports'][0]
        self.assertFalse(report['ok']);self.assertTrue(report['rollback']);self.assertEqual(report['readback'],'PASS')
        self.assertFalse(report['committed']);self.assertEqual(result['state']['m2_market_observations'],[])

    def test_readback_failure_retains_committed_observation(self):
        result=self.call(fault='readback');report=result['reports'][0]
        self.assertTrue(report['committed']);self.assertFalse(report['ok']);self.assertEqual(report['stage'],'readback')
        self.assertEqual(len(result['state']['m2_market_observations']),1)

    def test_ledger_unit_and_identity_drift_rejected_before_provider(self):
        state=copy.deepcopy(self.state);state['m2_assets'][0]['display_name']='Changed'
        for extra in [dict(bad_ledger=True),dict(bad_unit=True),dict(state=state)]:
            result=self.call(**extra);self.assertEqual(result['providers'],0);self.assertFalse(result['reports'][0]['committed'])

    def test_old_route_group_conflicts_and_acquisition_mismatch_fail_closed(self):
        for changed in [dict(asset_id='88'),dict(external_key='other')]:
            state=copy.deepcopy(self.state);state['m2_asset_source_routes'][0]['route_revision']='2'
            state['m2_asset_source_routes'].append(state['m2_asset_source_routes'][0]|dict(id='77',route_revision='1')|changed)
            result=self.call(state=state);self.assertEqual(result['providers'],0);self.assertFalse(result['reports'][0]['committed'])
        acquired=copy.deepcopy(self.acquired);acquired['provider_key']='wrong_provider'
        result=self.call(acquired=acquired);self.assertEqual(result['providers'],1);self.assertFalse(result['reports'][0]['committed'])

    def test_same_semantic_fact_on_another_route_is_not_reimported(self):
        fact=self.call()['state']['m2_market_observations'][0]
        altered=dict(fact,route_id='88')
        payload={k:altered[k] for k in live_bridge.writer.observation.FIELDS}
        altered['dedupe_key']=__import__('hashlib').sha256(live_bridge.writer.observation._canonical(payload)).hexdigest().upper()
        result=self.call(observations=[altered]);report=result['reports'][0]
        self.assertFalse(report['committed']);self.assertFalse(report['ok']);self.assertEqual(len(result['state']['m2_market_observations']),1)

    def test_corrupt_duplicate_payload_fails_closed(self):
        fact=self.call()['state']['m2_market_observations'][0];fact['price']='999.0000000000'
        result=self.call(observations=[fact]);self.assertFalse(result['reports'][0]['committed'])

    def test_exhaustive_snapshot_and_global_change_detection_remain_available(self):
        result=self.call(action='proof')
        self.assertTrue(result['reports'][0]['global_change_detected'])
        for table in self.state:self.assertTrue(any('FROM `'+table+'` ORDER BY' in q for q in result['queries']))
        code=(ROOT/'scripts/market_collector/live_persistence.php').read_text()
        self.assertIn("if($mode==='proof')return proofRun(",code)
        self.assertIn("$config['verification_mode']??'runtime'",code)

    def batch_inputs(self,size):
        state=copy.deepcopy(self.state)
        for table in ['m2_entities','m2_assets','m2_asset_identifiers','m2_asset_source_routes']:state[table]=[]
        entries=[];acquired=[]
        for i in range(size):
            m=copy.deepcopy(self.manifest);identity=isin(i+1);asset=str(100+i)
            m['identity'].update(canonical_name=f'Synthetic {i}',display_name=f'Synthetic {i}',identifier_value=identity,normalized_value=identity)
            m['instrument']=identity;m['route_evidence']['row']['isin']=identity
            state['m2_entities'].append(self.state['m2_entities'][0]|dict(id=asset,canonical_name=f'Synthetic {i}'))
            state['m2_assets'].append(self.state['m2_assets'][0]|dict(entity_id=asset,display_name=f'Synthetic {i}'))
            state['m2_asset_identifiers'].append(self.state['m2_asset_identifiers'][0]|dict(id=str(200+i),asset_id=asset,identifier_value=identity,normalized_value=identity))
            qualified=onboarding.route_input()|dict(asset_id=asset,evidence=m['route_evidence'])
            state['m2_asset_source_routes'].append(onboarding.call(action='route',routes=[],qualified=qualified,units=onboarding.UNITS)['result']['row']|dict(id=str(300+i)))
            item=copy.deepcopy(self.acquired);item['instrument']=identity
            body=json.loads(live_bridge.restore(item['response'])['payload_bytes']);body['isin']=identity
            item['response']['payload_bytes']={'$bytes':base64.b64encode(json.dumps(body).encode()).decode()}
            acquired.append(item);entries.append(dict(key=identity,fingerprint=identity,manifest=m))
        return dict(state=state,batch=entries,acquired_batch=acquired)

    def test_actual_runtime_batch_one_two_and_five_assets(self):
        for size in [1,2,5]:
            result=self.call(**self.batch_inputs(size));report=result['reports'][0]
            self.assertEqual(report['overall_status'],'COMPLETE',report)
            self.assertEqual(report['committed_count'],size);self.assertEqual(result['providers'],size)
            self.assertEqual(len(result['state']['m2_market_observations']),size)
            self.assertTrue(all(item['replay']=='DUPLICATE_UNCHANGED' and item['readback']=='PASS' for item in report['item_results']))

    def test_actual_middle_failure_keeps_only_previous_commits_and_stops(self):
        result=self.call(**self.batch_inputs(5),batch_fault_index=2);report=result['reports'][0]
        self.assertEqual(report['overall_status'],'PARTIAL_FAILED',report);self.assertEqual(report['committed_count'],2)
        self.assertEqual(len(result['state']['m2_market_observations']),2);self.assertEqual(result['providers'],3)
        self.assertEqual([x['status'] for x in report['item_results']],['COMPLETE','COMPLETE','FAILED','NOT_STARTED','NOT_STARTED'])


if __name__=='__main__':unittest.main()
