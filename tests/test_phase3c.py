"""Offline execution of the Phase-3C reference contract; no PDO or database."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/phase3c/market_flow.php'


class Phase3CTests(unittest.TestCase):
    def php(self, code, data):
        run = subprocess.run(['php', '-r', 'require $argv[1];'+code,
                              str(MODULE), json.dumps(data)], capture_output=True,
                             text=True, check=True)
        return json.loads(run.stdout)

    def setUp(self):
        self.assets = [1, 2, 3]
        self.sources = [10, 11]
        self.routes = [dict(id=101+i, asset_id=1+i, source_id=10) for i in range(3)]

    def observation(self, **changes):
        row = dict(asset_id=1, source_id=10, route_id=101, currency='EUR',
                   market_at='2026-01-01 12:00:00', observed_at='2026-01-01 12:00:01',
                   price='10.25', bid='10', ask='11', volume='2.5')
        row.update(changes)
        return row

    def writes(self, *operations):
        return self.php(r'''
$x=json_decode($argv[2],true,512,JSON_THROW_ON_ERROR);
$m=new \Mosa2\Phase3C\MarketFlow($x['assets'],$x['sources'],$x['routes']);$states=[];
foreach($x['operations'] as $op){$result=null;$error=null;
 try{$result=$m->write($op['row'],$op['fail']??false);}catch(InvalidArgumentException|RuntimeException $e){$error=$e->getMessage();}
 $states[]=['result'=>$result,'error'=>$error,'history'=>$m->history(),'current'=>$m->current()];
}echo json_encode($states,JSON_THROW_ON_ERROR);
''', dict(assets=self.assets, sources=self.sources, routes=self.routes,
          operations=[op if 'row' in op else dict(row=op) for op in operations]))

    def canonical(self, row):
        return self.php(r'''
$x=json_decode($argv[2],true,512,JSON_THROW_ON_ERROR);$r=\Mosa2\Phase3C\normalizeObservation($x);
echo json_encode(['row'=>$r,'canonical'=>\Mosa2\Phase3C\canonicalObservation($x),
 'digest'=>bin2hex(\Mosa2\Phase3C\dedupeKey($x)),'bytes'=>strlen(\Mosa2\Phase3C\dedupeKey($x))]);
''', row)

    def test_first_observation_sets_history_and_current(self):
        state = self.writes(self.observation())[0]
        self.assertIsNone(state['error'])
        self.assertEqual(len(state['history']), 1)
        self.assertEqual(state['result']['history'], 'inserted')
        self.assertEqual(state['result']['current'], 'updated')
        self.assertEqual(state['current']['1']['price'], '10.2500000000')
        self.assertNotIn('volume', state['current']['1'])
        self.assertEqual(next(iter(state['history'].values()))['volume'], '2.50000000')

    def test_identical_observation_is_noop(self):
        first, repeat = self.writes(self.observation(), self.observation())
        self.assertEqual(repeat['result']['history'], 'duplicate')
        self.assertEqual(repeat['result']['current'], 'unchanged')
        self.assertEqual(first['history'], repeat['history'])
        self.assertEqual(first['current'], repeat['current'])

    def test_newer_market_time_updates_current(self):
        first, latest = self.writes(self.observation(), self.observation(
            market_at='2026-01-02 12:00:00', observed_at='2026-01-01 00:00:00', price='20'))
        self.assertEqual(len(latest['history']), 2)
        self.assertEqual(latest['current']['1']['price'], '20.0000000000')
        self.assertEqual(latest['result']['current'], 'updated')
        for key, row in first['history'].items():
            self.assertEqual(latest['history'][key], row)

    def test_older_market_time_never_resets_current_even_if_observed_later(self):
        first, older = self.writes(self.observation(), self.observation(
            market_at='2025-12-31 12:00:00', observed_at='2026-01-03 12:00:00', price='9'))
        self.assertEqual(len(older['history']), 2)
        self.assertEqual(older['current'], first['current'])
        self.assertEqual(older['result']['current'], 'unchanged')

    def test_same_market_time_newer_observed_time_updates_current(self):
        first, later = self.writes(self.observation(), self.observation(observed_at='2026-01-01 12:00:02'))
        self.assertEqual(len(later['history']), 2)
        self.assertEqual(later['result']['current'], 'updated')
        self.assertNotEqual(first['current'], later['current'])
        self.assertEqual(later['current']['1']['observed_at'], '2026-01-01 12:00:02.000000')

    def test_identical_times_different_payload_keep_current(self):
        first, tied = self.writes(self.observation(), self.observation(price='12'))
        self.assertEqual(len(tied['history']), 2)
        self.assertEqual(first['current'], tied['current'])
        self.assertEqual(tied['result']['current'], 'unchanged')

    def test_older_observed_time_at_same_market_time_keeps_current(self):
        first, older = self.writes(self.observation(), self.observation(observed_at='2026-01-01 12:00:00', price='12'))
        self.assertEqual(first['current'], older['current'])
        self.assertEqual(len(older['history']), 2)

    def assert_rejected_without_changes(self, bad, reason):
        first, rejected = self.writes(self.observation(), bad)
        self.assertEqual(rejected['error'], reason)
        self.assertIsNone(rejected['result'])
        self.assertEqual(rejected['history'], first['history'])
        self.assertEqual(rejected['current'], first['current'])

    def test_route_asset_mismatch_is_atomic(self):
        self.assert_rejected_without_changes(self.observation(asset_id=2), 'route_asset')

    def test_route_source_mismatch_is_atomic(self):
        self.assert_rejected_without_changes(self.observation(source_id=11), 'route_source')

    def test_unknown_asset_is_atomic(self):
        self.assert_rejected_without_changes(self.observation(asset_id=99), 'unknown_asset')

    def test_unknown_source_is_atomic(self):
        self.assert_rejected_without_changes(self.observation(source_id=99), 'unknown_source')

    def test_unknown_route_is_atomic(self):
        self.assert_rejected_without_changes(self.observation(route_id=99), 'unknown_route')

    def test_failure_between_history_and_current_rolls_back(self):
        for seed in ([], [self.observation()]):
            with self.subTest(seeded=bool(seed)):
                states = self.writes(*seed, dict(row=self.observation(market_at='2026-01-02 12:00:00'), fail=True))
                failed = states[-1]
                self.assertEqual(failed['error'], 'simulated_after_history')
                self.assertEqual(failed['history'], states[0]['history'] if seed else [])
                self.assertEqual(failed['current'], states[0]['current'] if seed else [])

    def test_three_assets_have_separate_current_and_dedupe(self):
        states = self.writes(*(self.observation(asset_id=i, route_id=100+i) for i in (1, 2, 3)),
                             self.observation(price='20', market_at='2026-01-02 12:00:00'))
        before, after = states[2:]
        self.assertEqual(len(after['history']), 4)
        self.assertEqual(len(after['current']), 3)
        for asset in ('2', '3'):
            self.assertEqual(before['current'][asset], after['current'][asset])
        self.assertEqual(len({s['result']['dedupe_key'] for s in states[:3]}), 3)
        self.assertEqual(after['current']['1']['price'], '20.0000000000')

    def test_canonical_payload_and_exact_sha256_are_public_contract(self):
        result = self.canonical(self.observation())
        expected = 'mosa2-observation-v1\n'+json.dumps(dict(
            asset_id='1', source_id='10', route_id='101', currency='EUR',
            market_at='2026-01-01 12:00:00.000000', observed_at='2026-01-01 12:00:01.000000',
            price='10.2500000000', bid='10.0000000000', ask='11.0000000000', volume='2.50000000'),
            separators=(',', ':'))
        self.assertEqual(result['canonical'], expected)
        self.assertEqual(result['digest'], hashlib.sha256(expected.encode('ascii')).hexdigest())
        self.assertEqual(result['bytes'], 32)
        self.assertEqual(self.canonical(dict(reversed(list(self.observation().items())))), result)

    def test_each_identity_field_changes_digest(self):
        original = self.canonical(self.observation())['digest']
        alternatives = dict(asset_id=2, source_id=11, route_id=102, currency='USD',
                            market_at='2026-01-02 12:00:00', observed_at='2026-01-01 12:00:02',
                            price='10.26', bid='9', ask='12', volume='2.6')
        for field, value in alternatives.items():
            with self.subTest(field=field):
                self.assertNotEqual(self.canonical(self.observation(**{field: value}))['digest'], original)

    def test_null_decimal_and_input_order_canonicalization(self):
        a = self.observation(bid=None, ask=None, volume='-0.0000000000')
        b = self.observation(asset_id='0001', source_id='0010', route_id='0101',
                             price='+0010.250000000000', bid=None, ask=None, volume=0,
                             market_at='2026-01-01 12:00:00.0')
        self.assertEqual(self.canonical(a), self.canonical(b))
        self.assertNotEqual(self.canonical(a)['digest'], self.canonical(dict(a, volume=None))['digest'])
        first, repeat = self.writes(a, b)
        self.assertEqual(repeat['result']['history'], 'duplicate')
        self.assertEqual(first['current'], repeat['current'])

    def test_decimal_precision_and_sign_comparison_without_float(self):
        row = self.observation(price='999999999999999999.9999999999',
                               bid='-10', ask='-2', volume='999999999999999999999999.99999999')
        self.assertIsNone(self.writes(row)[0]['error'])
        for value in ('1000000000000000000', '0.00000000001'):
            self.assert_rejected_without_changes(self.observation(price=value), 'decimal_precision')
        self.assert_rejected_without_changes(self.observation(bid='-2', ask='-10'), 'bid_ask')

    def test_invalid_payload_values_are_rejected_atomically(self):
        cases = [({'price': '0'}, 'price'), ({'price': '-1'}, 'price'),
                 ({'price': 10.25}, 'decimal_type'), ({'price': True}, 'decimal_type'),
                 ({'price': '1e1'}, 'decimal_format'), ({'price': '1,25'}, 'decimal_format'),
                 ({'price': 'NaN'}, 'decimal_format'), ({'price': None}, 'decimal_null'),
                 ({'bid': '12', 'ask': '11'}, 'bid_ask'), ({'currency': 'eur'}, 'currency'),
                 ({'volume': '1000000000000000000000000'}, 'decimal_precision'),
                 ({'volume': '0.000000001'}, 'decimal_precision')]
        for changes, reason in cases:
            with self.subTest(changes=changes):
                self.assert_rejected_without_changes(self.observation(**changes), reason)
        for row in (dict(self.observation(), unexpected='ignored?'),
                    {k: v for k, v in self.observation().items() if k != 'volume'}):
            self.assert_rejected_without_changes(row, 'observation_fields')

    def test_strict_utc_calendar_and_microseconds(self):
        for value in ('2026-02-29 00:00:00', '2026-01-01 24:00:00',
                      '2026-01-01T12:00:00Z', '2026-01-01 12:00:00+02:00',
                      '2026-01-01 12:00:00.1234567', '0000-01-01 00:00:00'):
            with self.subTest(value=value):
                self.assert_rejected_without_changes(self.observation(market_at=value), 'utc_timestamp')
        first, later = self.writes(self.observation(observed_at='2026-01-01 12:00:01.000001'),
                                  self.observation(observed_at='2026-01-01 12:00:01.000002'))
        self.assertEqual(later['result']['current'], 'updated')
        self.assertNotEqual(first['current'], later['current'])
        self.assertIsNone(self.writes(self.observation(market_at='2024-02-29 00:00:00'))[0]['error'])

    def test_ids_are_unsigned_bigints_without_float_rounding(self):
        for value in (0, -1, True, 1.0, '1e0', '18446744073709551616'):
            with self.subTest(value=value):
                self.assert_rejected_without_changes(self.observation(asset_id=value), 'identifier')
        self.assets = ['18446744073709551615']
        self.routes = [dict(id=101, asset_id=self.assets[0], source_id=10)]
        state = self.writes(self.observation(asset_id=self.assets[0]))[0]
        self.assertIsNone(state['error'])
        self.assertIn(self.assets[0], state['current'])

    def test_cross_route_switch_is_rejected_without_arbitration(self):
        self.routes.append(dict(id=201, asset_id=1, source_id=11))
        self.assert_rejected_without_changes(self.observation(source_id=11, route_id=201), 'selected_route_changed')

    def test_input_and_returned_snapshots_cannot_mutate_history(self):
        self.assertTrue(self.php(r'''
$x=json_decode($argv[2],true);$m=new \Mosa2\Phase3C\MarketFlow([1],[10],[['id'=>101,'asset_id'=>1,'source_id'=>10]]);
$m->write($x);$before=[$m->history(),$m->current()];$x['price']='999';
$h=$m->history();$key=array_key_first($h);$h[$key]['price']='888';$c=$m->current();$c[1]['price']='777';
echo json_encode([$m->history(),$m->current()]===$before);
''', self.observation()))

    def test_migrations_unchanged_and_reference_lints(self):
        for file, digest in [('0001_core_asset_identity.sql', '9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd'),
                             ('0002_market_current_history.sql', '205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee')]:
            self.assertEqual(hashlib.sha256((ROOT/'docs/database/migrations'/file).read_bytes()).hexdigest(), digest)
        run = subprocess.run(['php', '-l', str(MODULE)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
        source = MODULE.read_text()
        self.assertNotIn('new PDO', source)
        self.assertNotIn('mysqli', source)
        self.assertNotIn('file_get_contents', source)


if __name__ == '__main__':
    unittest.main()
