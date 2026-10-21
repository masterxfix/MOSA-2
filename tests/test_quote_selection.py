"""Shared Current/Observations contract. All PNE/Zeiss values are synthetic."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.market_current import planner
import test_market_current as fixtures
from test_observation_v2_writer_phase3 import row, route, CREATED, qualified_synthetic_manifest

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [('DE000A0JBPG2', '101', '301'), ('DE0005313704', '102', '302')]


class QuoteSelectionTests(unittest.TestCase):
    def setUp(self):
        self.builder = fixtures.CurrentTests()
        self.builder.setUp()

    def data(self, isin, asset, physical, unit='EUR'):
        raw = row(unit, asset_id=asset, route_id=physical)
        r = route(raw)['route'] | dict(route_type='quote', priority='0', enabled='0')
        return dict(isin=isin, route=r, now=CREATED, facts=[self.builder.fact(raw)],
                    approval=dict(route_sha256=planner.route_hash(r), approved_at=CREATED,
                                  allow_disabled_projection=True))

    def php(self, data):
        request = dict(data, previous=data.get('current_fact'))
        result = subprocess.run(['php', str(ROOT/'tests/fixtures/quote_selection.php'), str(ROOT)],
            input=json.dumps(request), capture_output=True, text=True, check=True)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout)

    def agrees(self, data, decision):
        current = planner.plan(data)
        read = self.php(data)
        self.assertTrue(read['ok'], read)
        self.assertEqual(current['decision'], decision)
        self.assertEqual(read['selection']['decision'], decision)
        fact = read['selection']['fact']
        if fact is None:
            self.assertIsNone(current['values'])
        else:
            for key in ('price', 'market_at', 'observed_at', 'quote_unit_key', 'currency'):
                self.assertEqual(current['values'][key], fact[key])
        return current, read

    def test_pne_and_carl_zeiss_all_five_decisions(self):
        for scenario in SCENARIOS:
            with self.subTest(isin=scenario[0]):
                data = self.data(*scenario)
                current, read = self.agrees(data, 'INSERT')
                self.assertEqual(current['values']['observation_id'], read['item']['observation_id'])
                data.update(current=current['values'], current_fact=data['facts'][0])
                self.agrees(data, 'UNCHANGED')
                empty = data | dict(facts=[])
                self.agrees(empty, 'UNCHANGED')
                self.agrees(self.data(*scenario) | dict(facts=[]), 'MISSING')
                raw = row(asset_id=scenario[1], route_id=scenario[2],
                          market_at='2025-12-31 23:59:59', observed_at='2026-01-01 00:00:04')
                data['facts'] = [self.builder.fact(raw, '402')]
                self.agrees(data, 'UNCHANGED_OLDER')
                raw.update(market_at='2026-01-01 00:00:00', price='125')
                data['facts'] = [self.builder.fact(raw, '403')]
                current, read = self.agrees(data, 'UPDATE')
                self.assertEqual(current['values']['observation_id'], read['item']['observation_id'])

    def test_pne_zeiss_order_and_market_age_in_both_views(self):
        for scenario in SCENARIOS:
            data = self.data(*scenario)
            older = row(asset_id=scenario[1], route_id=scenario[2], market_at='2025-12-31 23:59:59',
                        observed_at='2026-01-01 00:59:59', price='900')
            data['facts'].append(self.builder.fact(older, '999'))
            data['now'] = '2026-01-01 01:00:00.000000'
            for facts in (data['facts'], data['facts'][::-1]):
                current, read = self.agrees(data | dict(facts=facts), 'INSERT')
                self.assertEqual(read['item']['age_seconds'], 3600)
                self.assertEqual(read['item']['status'], 'stale')
                self.assertEqual(current['values']['observation_id'], '401')

    def test_invalid_native_v2_bindings_are_blocked_in_both_paths(self):
        data = self.data(*SCENARIOS[0])
        for key, value in [('id','0'), ('asset_id','102'), ('source_id','202'), ('route_id','302'),
                           ('observation_format_version','1'), ('dedupe_key','00'*32),
                           ('quote_unit_key','GBP'), ('quote_unit_version','2'), ('currency','GBP'),
                           ('quantity_basis_amount','1.00000000'), ('volume','1.00000000'),
                           ('bid','200.0000000000'), ('price','0.0000000000'),
                           ('observed_at','2025-12-31 23:59:59.000000')]:
            with self.subTest(key=key):
                bad = copy.deepcopy(data);bad['facts'][0][key] = value
                with self.assertRaises((ValueError, KeyError)):planner.plan(bad)
                self.assertFalse(self.php(bad)['ok'])
        bad = copy.deepcopy(data);del bad['facts'][0]['price']
        with self.assertRaises(KeyError):planner.plan(bad)
        self.assertFalse(self.php(bad)['ok'])

    def test_equal_time_conflicts_and_hash_case(self):
        data = self.data(*SCENARIOS[1])
        data['facts'].append(self.builder.fact(row(asset_id='102', route_id='302', price='999'), '999'))
        for facts in (data['facts'], data['facts'][::-1]):
            with self.assertRaisesRegex(ValueError, 'equal_time_conflict'):planner.plan(data | dict(facts=facts))
            self.assertIn('equal_time_conflict', self.php(data | dict(facts=facts))['failure'])
        data['facts'][1] = copy.deepcopy(data['facts'][0]);data['facts'][1]['id'] = '999'
        data['facts'][1]['dedupe_key'] = data['facts'][1]['dedupe_key'].lower()
        current, read = self.agrees(data, 'INSERT')
        self.assertEqual(current['values']['observation_id'], '999')
        self.assertEqual(read['item']['observation_id'], '999')

    def test_current_origin_conflict_and_clock_policy_are_shared(self):
        data = self.data(*SCENARIOS[0])
        data.update(current=planner.plan(data)['values'], current_fact=data['facts'][0])
        data['facts'] = [self.builder.fact(row(price='999'), '402')]
        with self.assertRaisesRegex(ValueError, 'equal_time_conflict'):planner.plan(data)
        self.assertIn('equal_time_conflict', self.php(data)['failure'])
        for market, observed in [('2026-01-01 00:00:02', '2026-01-01 00:00:01'),
                                  ('2026-01-01 00:00:06', '2026-01-01 00:00:06'),
                                  ('2026-01-01 00:00:00', '2026-01-01 00:05:06')]:
            bad = self.data(*SCENARIOS[0])
            bad['facts'] = [self.builder.fact(row(market_at=market, observed_at=observed))]
            with self.assertRaisesRegex(ValueError, 'quote_clock'):planner.plan(bad)
            self.assertIn('quote_clock', self.php(bad)['failure'])

    def test_conflicting_older_times_are_blocked_even_when_newer_fact_exists(self):
        data = self.data(*SCENARIOS[0])
        raw = row(market_at='2025-12-31 23:59:59', price='1')
        data['facts'] += [self.builder.fact(raw, '402'), self.builder.fact(raw | dict(price='2'), '403')]
        with self.assertRaisesRegex(ValueError, 'equal_time_conflict'):
            planner.select(data['facts'], data['route'], data['now'])
        self.assertFalse(self.php(data)['ok'])

    def test_generic_units_are_native_without_equity_rules(self):
        for unit in ('EUR', 'GBP', 'GBX', 'POINT'):
            current, read = self.agrees(self.data(*SCENARIOS[0], unit=unit), 'INSERT')
            self.assertEqual(read['item']['unit'], unit)
            self.assertEqual(current['values']['price'], '123.4500000000')

    def test_existing_refresh_uses_current_planner_offline(self):
        items = [self.data(*scenario) for scenario in SCENARIOS]
        code = r'''require $argv[1].'/scripts/market_current/refresh.php';
            $d=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
            echo json_encode(\Mosa2\MarketCurrent\plans($d['config'],$d['items']),JSON_THROW_ON_ERROR);'''
        request = dict(items=items, config=dict(python=sys.executable, project=str(ROOT),
                                               runtime_path=os.environ['PATH']))
        process = subprocess.run(['php', '-r', code, str(ROOT)], input=json.dumps(request),
                                 capture_output=True, text=True, check=True)
        self.assertEqual(process.stderr, '')
        self.assertEqual([p['decision'] for p in json.loads(process.stdout)], ['INSERT', 'INSERT'])

    def test_dedupe_does_not_excuse_noncanonical_payload(self):
        import hashlib
        data = self.data(*SCENARIOS[0])
        data['facts'][0]['price'] = '0123.4500000000'
        payload = {k: data['facts'][0][k] for k in planner.CORE+planner.UNITS}
        data['facts'][0]['dedupe_key'] = hashlib.sha256(
            b'mosa2-observation-v2\n'+json.dumps(payload, separators=(',', ':')).encode()).hexdigest()
        with self.assertRaises(ValueError):planner.plan(data)
        self.assertFalse(self.php(data)['ok'])

    def test_generic_quantity_and_volume_with_explicit_synthetic_catalog(self):
        adapter = planner.writer.observation.catalog_module
        manifest = qualified_synthetic_manifest()
        catalog = adapter.UnitCatalog(manifest, manifest['package_sha256'])
        raw = row(quote_unit_key='SYNTH_QUOTE', quantity_basis_unit_key='SYNTH_QUANTITY',
                  quantity_basis_unit_version='1', quantity_basis_amount='2.00000000',
                  volume='5.00000000', volume_unit_key='SYNTH_VOLUME', volume_unit_version='1')
        r = route(raw)['route'] | dict(route_type='quote', priority='0', enabled='1')
        result = planner.writer.WriterPlanner(catalog, [route(raw)]).plan(raw, format_version=2,
            intent='NEW_NATIVE_V2', created_at=CREATED)
        fact = result['normalized'] | dict(id='401', observation_format_version='2',
            dedupe_key=result['dedupe_key'].hex().upper(), created_at=CREATED)
        data = dict(route=r, facts=[fact], now=CREATED,
            approval=dict(route_sha256=planner.route_hash(r), approved_at=CREATED))
        self.assertEqual(planner.plan(data, catalog)['decision'], 'INSERT')


if __name__ == '__main__':unittest.main()
