"""Synthetic snapshots only; integration ends at the existing offline writer."""
import ast
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import unittest
from unittest.mock import Mock, patch

from scripts.market_collector.collector import Collector, FixtureTransport
from scripts.market_collector.contracts import (ObservationCandidate, Request, RouteContract,
    TransportResponse, validate_payload)
from scripts.market_collector.normalizer import pipeline, raw_observation, writer
from scripts.market_collector.yahoo_chart import YahooChartSnapshotV1

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT/'tests/fixtures/market_collector'


class MarketCollectorTests(unittest.TestCase):
    def setUp(self):
        self.adapter = YahooChartSnapshotV1()
        self.catalog = writer.observation.catalog_module.normative_catalog()
        self.created = '2001-01-01 10:06:00.000000'

    def inputs(self, unit='EUR', payload=None):
        symbol = 'SYNTH-EUR' if unit == 'EUR' else 'SYNTH-GBX.L'
        request = Request(self.adapter.provider_key,'201','301','synthetic-snapshot',
                          '2001-01-01 10:04:00.000000',symbol)
        route = dict(id='301',asset_id='101',source_id='201',route_revision='1',
            unit_contract_version='mosa2-market-unit-v1',quote_unit_key=unit,quote_unit_version='1',
            quantity_basis_unit_key=None,quantity_basis_unit_version=None,quantity_basis_amount=None,
            volume_unit_key=None,volume_unit_version=None)
        contract = RouteContract(request.provider_key,symbol,2,route)
        if payload is None:payload=(FIXTURES/('eur_snapshot.json' if unit == 'EUR' else 'gbx_snapshot.json')).read_bytes()
        response = TransportResponse(payload,'2001-01-01 10:05:00.123456',200,'application/json; charset=utf-8')
        return request,contract,response

    def run_pipeline(self, inputs=None, adapters=None):
        request,route,response = inputs or self.inputs()
        return pipeline(request,route,FixtureTransport({request:response}),adapters or [self.adapter],
                        catalog=self.catalog,created_at=self.created)

    def payload_meta(self, **updates):
        document=json.loads((FIXTURES/'eur_snapshot.json').read_bytes())
        document['chart']['result'][0]['meta'].update(updates)
        return json.dumps(document).encode()

    def reject(self, inputs):
        result=self.run_pipeline(inputs)
        self.assertEqual(result['decision'],'REJECT');self.assertEqual(result['writer_decision'],'NOT_RUN')
        self.assertIsNone(result['dedupe_key']);self.assertIsNone(result['canonical_bytes'])
        return result

    def test_fixture_bytes_metadata_and_immutable_snapshots(self):
        request,route,response=self.inputs()
        bindings={request:response};transport=FixtureTransport(bindings);bindings.clear()
        payload=Collector([self.adapter]).collect(request,transport)
        self.assertIs(payload.payload_bytes,response.payload_bytes)
        self.assertEqual(payload.payload_bytes,(FIXTURES/'eur_snapshot.json').read_bytes())
        self.assertEqual((payload.http_status,payload.content_type),(response.http_status,response.content_type))
        with self.assertRaises(FrozenInstanceError):payload.payload_bytes=b'changed'
        with self.assertRaises(TypeError):route.route['id']='999'
        with self.assertRaises(ValueError):replace(response,payload_bytes=bytearray(response.payload_bytes))

    def test_exact_payload_sha_and_tampering_rejected(self):
        request,route,response=self.inputs()
        payload=Collector([self.adapter]).collect(request,FixtureTransport({request:response}))
        self.assertEqual(payload.payload_sha256,hashlib.sha256(response.payload_bytes).hexdigest())
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            self.adapter.normalize(replace(payload,payload_sha256='0'*64),route)
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            validate_payload(replace(payload,payload_bytes=payload.payload_bytes+b' '))

    def test_eur_end_to_end_uses_actual_phase3n_writer_and_plan_bytes(self):
        with patch.object(writer,'WriterPlanner',wraps=writer.WriterPlanner) as planner:
            result=self.run_pipeline()
        self.assertEqual(planner.call_count,1)
        self.assertEqual(result['decision'],'INSERT');self.assertEqual(result['writer_decision'],'INSERT')
        self.assertEqual(result['collector_status'],'COLLECTED');self.assertEqual(result['adapter_status'],'NORMALIZED')
        self.assertEqual(result['candidate'].native_price,'137.625')
        normalized=result['writer_plan']['normalized']
        self.assertEqual((normalized['currency'],normalized['quote_unit_key'],normalized['price']),('EUR','EUR','137.6250000000'))
        self.assertIs(result['canonical_bytes'],result['writer_plan']['canonical_bytes'])
        self.assertIs(result['dedupe_key'],result['writer_plan']['dedupe_key'])
        self.assertEqual(len(result['dedupe_key']),32)
        self.assertEqual(result['route_binding']['route_id'],'301')

    def test_gbx_native_snapshot_both_yahoo_spellings_no_division(self):
        for spelling in (b'GBp',b'GBX'):
            request,route,response=self.inputs('GBX')
            response=replace(response,payload_bytes=response.payload_bytes.replace(b'GBp',spelling))
            with self.subTest(spelling=spelling):
                result=self.run_pipeline((request,route,response));self.assertEqual(result['decision'],'INSERT')
                self.assertEqual(result['candidate'].provider_unit,'GBX');self.assertEqual(result['candidate'].native_price,'246.80')
                normalized=result['writer_plan']['normalized']
                self.assertEqual((normalized['currency'],normalized['quote_unit_key'],normalized['quote_unit_version']),('GBP','GBX','1'))
                self.assertEqual(normalized['price'],'246.8000000000')

    def test_times_and_payload_field_provenance_remain_distinct(self):
        result=self.run_pipeline();candidate=result['candidate'];provenance=dict(candidate.provenance)
        self.assertEqual(candidate.market_at,'2001-01-01 10:00:00.000000')
        self.assertEqual(candidate.observed_at,'2001-01-01 10:05:00.123456')
        self.assertNotEqual(candidate.market_at,candidate.observed_at)
        for key in ('provider_key','request_key','payload_sha256'):
            self.assertEqual(provenance[key],getattr(result['collected_payload'],key))
        self.assertEqual(provenance['price_field_source'],'$.chart.result[0].meta.regularMarketPrice')
        self.assertEqual(provenance['time_field_source'],'$.chart.result[0].meta.regularMarketTime')

    def test_snapshot_ignores_daily_volume_bars_and_produces_no_fx_or_current(self):
        result=self.run_pipeline();row=result['writer_plan']['normalized']
        self.assertIsNone(result['candidate'].native_volume);self.assertIsNone(row['volume'])
        self.assertTrue(all(row[f] is None for f in writer.UNIT_FIELDS[3:]))
        self.assertEqual(set(row),set(writer.observation.FIELDS))
        for field in ('fx','derived','current','bars','observations'):
            self.assertNotIn(field,result);self.assertNotIn(field,row)

    def test_invalid_json_and_ambiguous_members_rejected(self):
        for body in (b'{broken',b'{"chart":null,"chart":{}}'):
            with self.subTest(body=body):self.reject(self.inputs(payload=body))

    def test_missing_or_ambiguous_result_and_missing_meta_rejected(self):
        for body in (b'{}',b'{"chart":{"result":[]}}',b'{"chart":{"result":[{}]}}'):
            with self.subTest(body=body):self.reject(self.inputs(payload=body))

    def test_symbol_and_request_route_context_mismatches_rejected(self):
        self.reject(self.inputs(payload=self.payload_meta(symbol='OTHER-SYNTH')))
        request,route,response=self.inputs()
        self.reject((replace(request,instrument='OTHER-SYNTH'),route,response))

    def test_missing_price_rejected(self):
        document=json.loads((FIXTURES/'eur_snapshot.json').read_bytes())
        del document['chart']['result'][0]['meta']['regularMarketPrice']
        self.reject(self.inputs(payload=json.dumps(document).encode()))

    def test_integer_price_above_binary_float_precision_stays_exact(self):
        result=self.run_pipeline(self.inputs(payload=self.payload_meta(regularMarketPrice=9007199254740993)))
        self.assertEqual(result['decision'],'INSERT')
        self.assertEqual(result['candidate'].native_price,'9007199254740993')
        self.assertEqual(result['writer_plan']['normalized']['price'],'9007199254740993.0000000000')

    def test_invalid_provider_time_rejected(self):
        for epoch in ('not-an-epoch',10**20,True):
            with self.subTest(epoch=epoch):self.reject(self.inputs(payload=self.payload_meta(regularMarketTime=epoch)))

    def test_provider_unit_route_mismatch_rejected(self):
        self.reject(self.inputs(payload=self.payload_meta(currency='GBP')))

    def test_legacy_route_is_not_upgraded(self):
        request,route,response=self.inputs()
        legacy=dict(route.route);legacy.update(dict.fromkeys(writer.UNIT_FIELDS))
        self.reject((request,RouteContract(route.provider_key,route.instrument,1,legacy),response))

    def test_wrong_identity_and_nonpositive_revision_rejected(self):
        request,route,response=self.inputs()
        self.reject((replace(request,source_id='202'),route,response))
        self.reject((request,RouteContract(route.provider_key,route.instrument,2,dict(route.route,route_revision='0')),response))

    def test_transport_failure_and_missing_fixture_fail_closed(self):
        request,route,response=self.inputs()
        for failed in (replace(response,http_status=503),replace(response,transport_status='ERROR',transport_error='fixture_timeout')):
            self.reject((request,route,failed))
        result=pipeline(request,route,FixtureTransport({}),[self.adapter],catalog=self.catalog,created_at=self.created)
        self.assertEqual(result['decision'],'REJECT');self.assertEqual(result['collector_status'],'REJECT')

    def test_candidate_hash_provenance_and_observed_time_are_bound(self):
        request,route,response=self.inputs()
        payload=Collector([self.adapter]).collect(request,FixtureTransport({request:response}))
        candidate=self.adapter.normalize(payload,route)
        for changed in (replace(candidate,payload_sha256='0'*64),replace(candidate,provenance=()),
                        replace(candidate,observed_at=self.created)):
            with self.assertRaises(ValueError):raw_observation(changed,payload,route,self.catalog)

    def test_generic_adapter_and_catalog_currency_including_point(self):
        class SyntheticPointAdapter:
            provider_key='synthetic_point_v1'
            def normalize(self,payload,route):
                return ObservationCandidate('101',payload.source_id,payload.route_id,'2001-01-01 10:00:00.000000',
                    payload.collected_at,'42',None,None,None,'POINT',payload.payload_sha256,
                    (('provider_key',payload.provider_key),('request_key',payload.request_key),
                     ('payload_sha256',payload.payload_sha256),('price_field_source','$.value'),('time_field_source','$.time')))
        request,route,response=self.inputs()
        adapter=SyntheticPointAdapter();request=replace(request,provider_key=adapter.provider_key)
        route=RouteContract(adapter.provider_key,route.instrument,2,dict(route.route,quote_unit_key='POINT'))
        response=replace(response,payload_bytes=b'{"value":42,"time":978343200}')
        result=self.run_pipeline((request,route,response),[adapter]);self.assertEqual(result['decision'],'INSERT')
        self.assertIsNone(result['writer_plan']['normalized']['currency'])
        # GBP is a provider spelling as well as a route/catalog unit.
        request,route,response=self.inputs()
        route=RouteContract(route.provider_key,route.instrument,2,dict(route.route,quote_unit_key='GBP'))
        response=replace(response,payload_bytes=self.payload_meta(currency='GBP'))
        self.assertEqual(self.run_pipeline((request,route,response))['writer_plan']['normalized']['currency'],'GBP')

    def test_no_network_database_or_hidden_provider_fallback(self):
        with patch.object(socket,'socket',side_effect=AssertionError('no network')), \
             patch.object(sqlite3,'connect',side_effect=AssertionError('no database')):
            self.assertEqual(self.run_pipeline()['decision'],'INSERT')
        forbidden={'socket','requests','urllib','http','sqlite3','mysql','pymysql'}
        for path in (ROOT/'scripts/market_collector').glob('*.py'):
            tree=ast.parse(path.read_text())
            imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
            imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
            self.assertFalse({name.split('.')[0] for name in imports if name} & forbidden)
        core=(ROOT/'scripts/market_collector/collector.py').read_text()
        for word in ('yahoo','GBX','currency','regularMarket','native_price','WriterPlanner'):
            self.assertNotIn(word,core)


if __name__=='__main__':unittest.main()
