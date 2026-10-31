"""One explicit source transition using real writer and quote-selection contracts."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from scripts.market_current import planner as current
from test_observation_v2_writer_phase3 import row, route, CREATED

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('php'), 'PHP required')
class CurrentRouteTransitionTests(unittest.TestCase):
    def fact(self, value, identity):
        result = current.writer.WriterPlanner(
            current.writer.observation.catalog_module.normative_catalog(), [route(value)]
        ).plan(value, format_version=2, intent='NEW_NATIVE_V2', created_at=CREATED)
        self.assertEqual(result['decision'], 'INSERT', result)
        return result['normalized'] | dict(id=identity, observation_format_version='2',
            dedupe_key=result['dedupe_key'].hex().upper(), created_at=CREATED)

    def setUp(self):
        old_raw = row()
        self.old_route = route(old_raw)['route'] | dict(route_type='quote', priority='0', enabled='0')
        self.old_fact = self.fact(old_raw, '401')
        old = current.plan(dict(route=self.old_route, facts=[self.old_fact], now=CREATED,
            approval=dict(route_sha256=current.route_hash(self.old_route), approved_at=CREATED,
                          allow_disabled_projection=True)))['values']
        self.new_raw = row(source_id='202', route_id='302', price='124', bid='123', ask='125',
                           market_at='2026-01-01 00:00:02', observed_at='2026-01-01 00:00:03')
        self.new_route = route(self.new_raw)['route'] | dict(route_type='quote', priority='0', enabled='0')
        self.data = dict(route=self.new_route, current_route=self.old_route, current=old,
            current_fact=self.old_fact, facts=[self.fact(self.new_raw, '402')], now=CREATED,
            approval=dict(route_sha256=current.route_hash(self.new_route), approved_at=CREATED,
                          allow_disabled_projection=True, allow_route_transition=True,
                          previous_route_sha256=current.route_hash(self.old_route)))

    def test_preflight_then_newer_source_and_idempotent_replay(self):
        original = copy.deepcopy(self.data)
        empty = current.plan(self.data | dict(facts=[]))
        self.assertEqual(empty, dict(decision='UNCHANGED', values=self.data['current']))
        result = current.plan(self.data)
        self.assertEqual(result['decision'], 'UPDATE')
        self.assertEqual((result['values']['source_id'], result['values']['route_id'],
                          result['values']['observation_id']), ('202', '302', '402'))
        self.assertEqual(self.data, original)
        replay = copy.deepcopy(self.data)
        replay.update(current=result['values'], current_fact=self.data['facts'][0])
        replay.pop('current_route')
        self.assertEqual(current.plan(replay), dict(decision='UNCHANGED', values=result['values']))

    def test_transition_requires_explicit_approval_and_pins_previous_route(self):
        for key, value, reason in [('allow_route_transition', False, 'not_approved'),
                                   ('previous_route_sha256', '0' * 64, 'approval_drift')]:
            with self.subTest(key=key):
                data = copy.deepcopy(self.data)
                data['approval'][key] = value
                with self.assertRaisesRegex(ValueError, reason):
                    current.plan(data)
        data = copy.deepcopy(self.data)
        data.pop('current_route')
        with self.assertRaisesRegex(ValueError, 'previous_route_missing'):
            current.plan(data)

    def test_old_projection_and_asset_units_remain_validated(self):
        data = copy.deepcopy(self.data)
        data['current']['price'] = '999.0000000000'
        with self.assertRaisesRegex(ValueError, 'projection_drift'):
            current.plan(data)
        data = copy.deepcopy(self.data)
        data['current_fact']['dedupe_key'] = '0' * 64
        with self.assertRaises(ValueError):
            current.plan(data)
        for field, value, reason in [('asset_id', '999', 'transition_asset'),
                                      ('quote_unit_key', 'GBP', 'transition_units')]:
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data['route'][field] = value
                data['approval']['route_sha256'] = current.route_hash(data['route'])
                with self.assertRaisesRegex(ValueError, reason):
                    current.plan(data)

    def test_older_or_equal_source_time_never_replaces_current(self):
        for market, observed, decision in [
            ('2025-12-31 23:59:59', '2026-01-01 00:00:04', 'UNCHANGED_OLDER'),
            ('2026-01-01 00:00:00', '2026-01-01 00:00:01', 'UNCHANGED')]:
            with self.subTest(market=market):
                raw = self.new_raw | dict(market_at=market, observed_at=observed)
                data = self.data | dict(facts=[self.fact(raw, '402')])
                self.assertEqual(current.plan(data), dict(decision=decision, values=self.data['current']))

    def test_php_inputs_loads_old_route_by_current_provenance(self):
        request = dict(routes=[self.old_route, self.new_route], current=self.data['current'],
            old_fact=self.old_fact, facts=self.data['facts'], approval=self.data['approval'], now=CREATED)
        request['approval'] = request['approval'] | dict(route_id=self.new_route['id'])
        process = subprocess.run(['php', str(ROOT/'tests/fixtures/current_route_transition.php'), str(ROOT)],
            input=json.dumps(request), capture_output=True, text=True, check=True)
        self.assertEqual(process.stderr, '')
        result = json.loads(process.stdout)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['items'][0]['current_route'], self.old_route)
        self.assertEqual(current.plan(result['items'][0])['decision'], 'UPDATE')
        old_lookups = [x for x in result['queries'] if 'AND asset_id=? AND source_id=?' in x['sql']]
        self.assertEqual(len(old_lookups), 1)
        self.assertEqual(old_lookups[0]['args'], ['301', '101', '201'])
        self.assertTrue(old_lookups[0]['sql'].endswith(' FOR UPDATE'))


if __name__ == '__main__':
    unittest.main()
