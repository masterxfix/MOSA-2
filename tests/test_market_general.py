"""Dynamic catalog -> real batch/Observation v2 -> Current transaction -> web reader."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_market_onboarding as catalog
import test_tradegate_manifest as manifests
import test_tradegate_collector as tradegate
import test_market_collector_v1 as frankfurt
from test_market_live_batch import isin
from scripts.market_collector import live_bridge

ROOT = Path(__file__).resolve().parents[1]


class GeneralMarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template = catalog.state(True)
        state = {k: [] for k in template}
        values = manifests.call(action='source', sources=[], now=manifests.NOW)['result']['values']
        state.update(m2_sources=[dict(id='301', **values), dict(id='302', source_key='provider:boerse_frankfurt_api',
                     enabled='1', source_type='market_data', display_name='Frankfurt')], m2_asset_source_routes=[],
                     m2_units=[dict(unit_key='EUR', unit_version='1', unit_contract_version='mosa2-market-unit-v1',
                                   monetary_currency_code='EUR', status='frozen')])
        cls.acquired = {}
        for i in range(5):
            identity = str(101+i); instrument = isin(i+1); name = 'Registered equity '+str(i)
            state['m2_entities'].append(dict(template['m2_entities'][0], id=identity, canonical_name=name))
            state['m2_assets'].append(dict(template['m2_assets'][0], entity_id=identity, display_name=name))
            state['m2_asset_identifiers'].append(dict(template['m2_asset_identifiers'][0], id=str(201+i),
                asset_id=identity, normalized_value=instrument, identifier_value=instrument))
            if i < 4:
                m = manifests.call(action='manifest', state=state, selection=dict(isin=instrument, name=name))['result']
                plan = m['plan']['route']; fixture = tradegate.TradegateCollectorTests(); fixture.setUp()
                response = replace(fixture.response, payload_bytes=tradegate.BODY.replace(b'DE0007030009', instrument.encode()))
                adapter_module = 'scripts.market_collector.tradegate'; adapter_class = 'TradegateQuoteV1'
            else:
                evidence = dict(sample_id='TEST', source_reference='qualified:test', family='frankfurt_snapshot',
                    row=dict(isin=instrument, provider_key='boerse_frankfurt_api', venue_key='boerse_frankfurt',
                             currency='EUR', quote_variant=None, series='snapshot', observation_kind='market_quote'),
                    proof=dict(external_identity=dict(isin=instrument, venue='boerse_frankfurt'), route_reference='qualified:test', unit_class='currency_per_instrument'))
                plan = catalog.call(action='route', routes=[], qualified=dict(asset_id=identity, source_id='302',
                    route_type='quote', priority=0, enabled=0, evidence=evidence), units=catalog.UNITS)['result']
                fixture = frankfurt.FrankfurtCollectorTests(); fixture.setUp()
                body = json.loads(fixture.response.payload_bytes); body['isin'] = instrument
                response = replace(fixture.response, payload_bytes=json.dumps(body).encode())
                adapter_module = 'scripts.market_collector.boerse_frankfurt'; adapter_class = 'FrankfurtSnapshotV1'
            state = catalog.call(action='materialize', state=state, plan=plan, asset_id=identity)['result']['after']
            cls.acquired[instrument] = dict(provider_requests=1, adapter_module=adapter_module, adapter_class=adapter_class,
                provider_key=fixture.adapter.provider_key, request_key='quote:'+instrument,
                requested_at=fixture.request.requested_at, instrument=instrument, response=live_bridge.transport(asdict(response)))
        cls.state = state

    def call(self, **extra):
        with tempfile.TemporaryDirectory(prefix='mosa-general-') as private:
            data = dict(action='general', state=self.state, acquired_by_isin=self.acquired, private_root=private.replace('\\','/'),
                        config=dict(python=sys.executable, project=str(ROOT), php='php', runtime_path=os.environ['PATH'])) | extra
            data['observations'] = data['state'].get('m2_market_observations', [])
            reply = subprocess.run(['php', str(ROOT/'tests/market_runtime_fixture.php')], input=json.dumps(data),
                                   capture_output=True, text=True, check=True)
            self.assertEqual(reply.stderr, '')
            return json.loads(reply.stdout)

    def test_full_dynamic_five_mixed_providers_dedupe_current_and_web(self):
        result = self.call(runs=2)
        self.assertEqual(result['providers'], 10)  # Offline doubles only: two five-asset batches.
        for report in result['reports']:
            self.assertTrue(report['ok'], report)
            self.assertEqual(report['protection'], 'PASS')
            self.assertEqual(report['current']['readback'], 'PASS')
        self.assertEqual(len(result['state']['m2_market_observations']), 5)
        self.assertEqual(len(result['state']['m2_market_current']), 5)
        self.assertEqual([x['writer'] for x in result['reports'][1]['batch']['item_results']], ['DUPLICATE_UNCHANGED']*5)
        self.assertEqual(result['reports'][1]['current']['decisions'], ['UNCHANGED']*5)
        self.assertEqual(result['state']['m2_asset_source_routes'], self.state['m2_asset_source_routes'])
        self.assertEqual({r['source_id'] for r in result['state']['m2_market_observations']}, {'301','302'})
        for row in result['state']['m2_market_current']:
            code = "require $argv[1].'/api/read_model.php';$d=json_decode(stream_get_contents(STDIN),true);echo json_encode(\\Mosa2\\MarketRead\\present($d,'2026-11-02 17:00:00.000000',1800));"
            web = subprocess.run(['php','-r',code,str(ROOT)], input=json.dumps(row | dict(display_name='Registered equity',
                source_name='Qualified source',venue='Registered venue',valid_binding='1')), capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(web.stdout)['price'], row['price'])

    def test_single_requested_isin_from_five_qualified_assets(self):
        selected = self.state['m2_asset_identifiers'][0]['normalized_value']
        result = self.call(requested_isins=[selected], request_budget=1)
        self.assertEqual(result['providers'], 1)
        self.assertTrue(result['reports'][0]['ok'], result['reports'])
        self.assertEqual(len(result['state']['m2_market_observations']), 1)
        self.assertEqual(len(result['state']['m2_market_current']), 1)
        self.assertEqual(result['state']['m2_market_observations'][0]['asset_id'], '101')

    def test_partial_failure_stops_batch_and_never_projects_current(self):
        result = self.call(fail_provider=3)
        report = result['reports'][0]
        self.assertFalse(report['ok'])
        self.assertEqual(report['batch']['overall_status'], 'PARTIAL_FAILED')
        self.assertEqual(result['providers'], 3)
        self.assertEqual(len(result['state']['m2_market_observations']), 2)
        self.assertEqual(result['state']['m2_market_current'], [])

    def test_scope_mismatch_prevents_first_request(self):
        result = self.call(bad_scope=True)
        self.assertEqual(result['providers'], 0)
        self.assertEqual(result['reports'][0]['failure'], 'collection_authorized_routes')

    def test_disabled_routes_are_not_automatic(self):
        result = self.call(mode='automatic')
        self.assertEqual(result['providers'], 0)
        self.assertFalse(result['reports'][0]['ok'])

    def test_already_enabled_routes_work_without_route_mutation(self):
        active = deepcopy(self.state)
        for route in active['m2_asset_source_routes']:
            route['enabled'] = '1'
        result = self.call(state=active, mode='automatic')
        self.assertTrue(result['reports'][0]['ok'], result['reports'])
        self.assertEqual(result['state']['m2_asset_source_routes'], active['m2_asset_source_routes'])

    def test_explicit_priority_resolves_two_qualified_physical_sources(self):
        active = deepcopy(self.state)
        selected = dict(isin=active['m2_asset_identifiers'][0]['normalized_value'], name=active['m2_assets'][0]['display_name'])
        code = "require $argv[1].'/scripts/market_collector/actions_acceptance.php';$d=json_decode(stream_get_contents(STDIN),true);$m=\\Mosa2\\MarketAcceptance\\manifest($d['state'],$d['selected']);echo json_encode(\\Mosa2\\MarketLive\\completePlan($d['state'],$m)['route']['row']);"
        reply = subprocess.run(['php','-r',code,str(ROOT)], input=json.dumps(dict(state=active,selected=selected)),
                               text=True,capture_output=True,check=True)
        active['m2_asset_source_routes'].append(json.loads(reply.stdout) | dict(id='999'))
        for route in active['m2_asset_source_routes']:
            route['enabled'] = '1'
        result = self.call(state=active, mode='automatic')
        self.assertTrue(result['reports'][0]['ok'], result['reports'])
        first = next(x for x in result['state']['m2_market_observations'] if x['asset_id']=='101')
        self.assertEqual(first['source_id'], '301')
        self.assertEqual(result['state']['m2_asset_source_routes'], active['m2_asset_source_routes'])

    def test_older_observation_preserves_newer_current(self):
        first = self.call()
        state = first['state']; state['m2_schema_migrations'] = []
        acquired = deepcopy(self.acquired)
        key = next(iter(acquired))
        body = live_bridge.restore(acquired[key]['response'])
        body['payload_bytes'] = body['payload_bytes'].replace(b'01.09.2026 @', b'31.08.2026 @')
        acquired[key]['response'] = live_bridge.transport(body)
        result = self.call(state=state, acquired_by_isin=acquired)
        self.assertTrue(result['reports'][0]['ok'], result['reports'])
        self.assertEqual(result['state']['m2_market_current'], state['m2_market_current'])
        self.assertEqual(len(result['state']['m2_market_observations']), 6)

    def test_independent_readback_failure_is_not_success_or_retry(self):
        result = self.call(readback_fault=True)
        self.assertFalse(result['reports'][0]['ok'])
        self.assertEqual(result['reports'][0]['stage'], 'current')
        self.assertEqual(result['providers'], 5)
        self.assertEqual(result['reports'][0]['database_writes'], 10)


class CollectionAuthorizationTests(unittest.TestCase):
    def test_exact_scope_commit_and_attempt_are_bound_before_ssh(self):
        sys.path.insert(0, str(ROOT/'scripts'))
        from scripts import collector_actions as driver
        scope = json.dumps(dict(mode='manual', request_budget=5, source_priority=['provider:tradegate_bsx_mid'],
                                expected_isins=[isin(i+1) for i in range(5)]))
        env = dict(MOSA_MARKET_EXPECTED_COMMIT='a'*40, MOSA_MARKET_SCOPE=scope,
            MOSA_MARKET_AUTHORIZATION='MOSA2-MARKET-BATCH:'+'a'*40+':'+hashlib.sha256(scope.encode()).hexdigest(),
            GITHUB_SHA='a'*40, GITHUB_ACTIONS='true', GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_REF='refs/heads/main', GITHUB_REPOSITORY='masterxfix/MOSA-2')
        self.assertEqual(driver.collection_scope(env), json.loads(scope))
        for key in ('GITHUB_RUN_ATTEMPT','GITHUB_SHA','MOSA_MARKET_SCOPE','MOSA_MARKET_AUTHORIZATION'):
            bad = env | {key: 'invalid'}
            self.assertFalse(driver.execute_collection(bad)['ok'])


if __name__ == '__main__':
    unittest.main()
