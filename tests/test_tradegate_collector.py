"""The existing MOSA fixture through the generic MOSA-2 writer and Current reader."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from scripts.market_collector.collector import Collector, FixtureTransport
from scripts.market_collector.contracts import Request, RouteContract, TransportResponse, validate_payload
from scripts.market_collector.normalizer import pipeline, writer
from scripts.market_collector.tradegate import TradegateQuoteV1
from scripts.market_current import planner as current


ROOT = Path(__file__).resolve().parents[1]
BODY = (ROOT / 'tests/fixtures/market_collector/tradegate_quote.html').read_bytes()


class TradegateCollectorTests(unittest.TestCase):
    def setUp(self):
        self.adapter = TradegateQuoteV1()
        self.catalog = writer.observation.catalog_module.normative_catalog()
        self.request = Request(self.adapter.provider_key, '201', '301', 'tradegate-quote:DE0007030009',
                               '2026-09-01 10:00:20.000000', 'DE0007030009')
        row = dict(id='301', asset_id='101', source_id='201', route_revision='1',
            unit_contract_version='mosa2-market-unit-v1', quote_unit_key='EUR', quote_unit_version='1',
            quantity_basis_unit_key=None, quantity_basis_unit_version=None, quantity_basis_amount=None,
            volume_unit_key=None, volume_unit_version=None)
        self.route = RouteContract(self.adapter.provider_key, self.request.instrument, 2, row)
        self.response = TransportResponse(BODY, '2026-09-01 10:00:30.000000', 200, 'text/html; charset=UTF-8')
        self.created = '2026-09-01 10:00:31.000000'

    def run_pipeline(self, response=None, request=None, route=None, *, existing=()):
        request, route = request or self.request, route or self.route
        return pipeline(request, route, FixtureTransport({request: response or self.response}), [self.adapter],
                        catalog=self.catalog, created_at=self.created, existing=existing)

    def test_existing_mosa_fixture_reaches_writer_current_and_web(self):
        result = self.run_pipeline()
        self.assertEqual(result['decision'], 'INSERT', result)
        candidate = result['candidate']
        self.assertEqual((candidate.native_bid, candidate.native_ask, candidate.native_price),
                         ('187.2', '187.4', '187.3'))
        self.assertEqual(candidate.market_at, '2026-09-01 10:00:10.000000')
        self.assertEqual(candidate.observed_at, self.response.collected_at)
        self.assertEqual(candidate.payload_sha256, hashlib.sha256(BODY).hexdigest())
        self.assertEqual(dict(candidate.provenance)['quote_type'], 'mid')
        self.assertEqual(dict(candidate.provenance)['price_field_source'], '(Bid+Ask)/2')
        fact = result['writer_plan']['normalized'] | dict(id='401', observation_format_version='2',
            dedupe_key=result['dedupe_key'].hex().upper(), created_at=self.created)
        route = dict(self.route.route) | dict(route_type='quote', priority='0', enabled='1')
        inputs = dict(route=route, facts=[fact], now=self.created,
                      approval=dict(route_sha256=current.route_hash(route), approved_at=self.created))
        projection = current.plan(inputs)
        self.assertEqual(projection['decision'], 'INSERT')
        stored = projection['values']
        self.assertEqual((stored['observation_id'], stored['price'], stored['market_at']),
                         ('401', '187.3000000000', fact['market_at']))
        inputs.update(current=stored, current_fact=fact)
        self.assertEqual(current.plan(inputs)['decision'], 'UNCHANGED')
        web_row = stored | dict(display_name='Synthetic registered equity', source_name='Tradegate Mid',
                                venue='Tradegate BSX', valid_binding='1')
        code = "require $argv[1].'/api/read_model.php'; $d=json_decode(stream_get_contents(STDIN),true); echo json_encode(\\Mosa2\\MarketRead\\present($d['row'],$d['now'],60));"
        reply = subprocess.run(['php', '-r', code, str(ROOT)], input=json.dumps(dict(row=web_row, now=self.created)),
                               text=True, capture_output=True, check=True)
        self.assertEqual(reply.stderr, '')
        web = json.loads(reply.stdout)
        self.assertEqual(web['price'], stored['price'])
        self.assertEqual(web['market_at'], fact['market_at'] + 'Z')
        duplicate = self.run_pipeline(existing=[dict(format_version=2,
            payload=result['writer_plan']['normalized'], dedupe_key=result['dedupe_key'])])
        self.assertEqual(duplicate['decision'], 'DUPLICATE_UNCHANGED')

    def test_invalid_context_quotes_time_and_media_are_rejected(self):
        variations = [BODY.replace(b'DE0007030009', b'DE000A0JBPG2'),
            BODY.replace(b'<td>EUR</td>', b'<td>USD</td>'),
            BODY.replace(b'187,20', b'188,00'), BODY.replace(b'187,20', b'0,00'),
            BODY.replace(b'Letzte Aktualisierung:', b'Unqualified time:'),
            BODY.replace(b'12:00:10', b'12:05:10')]
        for body in variations:
            with self.subTest(body=body):
                result = self.run_pipeline(replace(self.response, payload_bytes=body))
                self.assertEqual(result['decision'], 'REJECT')
                self.assertEqual(result['rejected_stage'], 'adapter')
        for response in (replace(self.response, content_type='application/json'),
                         replace(self.response, http_status=429)):
            self.assertEqual(self.run_pipeline(response)['decision'], 'REJECT')
        payload = Collector([self.adapter]).collect(self.request, FixtureTransport({self.request:self.response}))
        with self.assertRaisesRegex(ValueError, 'JSON content type required'):
            validate_payload(payload)  # Existing JSON defaults are not broadened.
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.adapter.normalize(replace(payload, payload_sha256='0'*64), self.route)

    def test_generic_descriptor_exact_midpoint_and_unchanged_old_quote_time(self):
        for isin in ('DE0007030009', 'DE000A0JBPG2'):
            endpoint = self.adapter.live_request(isin, self.created)
            self.assertEqual(endpoint['url'], 'https://www.tradegatebsx.com/orderbuch.php?isin=' + isin)
            self.assertEqual(endpoint['request_key'], 'tradegate-quote:' + isin)
        with self.assertRaises(ValueError):
            self.adapter.live_request('DE0007030009&other=1', self.created)
        # German separators and decimal arithmetic; midpoint is never binary float rounded.
        body = BODY.replace(b'187,20', b'1.234,0000000001').replace(b'187,40', b'1.234,0000000003')
        result = self.run_pipeline(replace(self.response, payload_bytes=body))
        self.assertEqual(result['decision'], 'INSERT', result)
        self.assertEqual(result['candidate'].native_price, '1234.0000000002')
        later_request = replace(self.request, requested_at='2026-09-05 10:00:20.000000')
        later_response = replace(self.response, collected_at='2026-09-05 10:00:30.000000')
        payload = Collector([self.adapter]).collect(later_request, FixtureTransport({later_request:later_response}))
        candidate = self.adapter.normalize(payload, self.route)
        self.assertEqual(candidate.market_at, '2026-09-01 10:00:10.000000')
        self.assertEqual(candidate.observed_at, '2026-09-05 10:00:30.000000')


if __name__ == '__main__':
    unittest.main()
