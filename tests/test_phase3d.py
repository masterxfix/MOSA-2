"""Synthetic offline Phase-3D tests. No source samples, database or network."""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/phase3d/dry_run.php'


class Phase3DTests(unittest.TestCase):
    def entry(self, **changes):
        e = dict(sample_id='A1', source_reference='synthetic:1', family='synthetic',
                 row=dict(isin='US0378331005', provider_key='test_provider', venue_key='TEST',
                          symbol='SYNTH', currency='EUR', series='snapshot',
                          observation_kind='market_quote', quoted_at='2026-01-01 12:00:00',
                          collected_at='2026-01-01 12:00:01', last_price='10.25',
                          bid_price='10', ask_price='11', volume_units='999', turnover_original='1000'),
                 proof=dict(context_isin='US0378331005', unit_class='currency_per_instrument',
                            producer_reference='synthetic producer UTC contract',
                            market_at_semantics='utc', observed_at_semantics='utc',
                            external_identity=dict(symbol='SYNTH', exchange='TEST'),
                            route_reference='synthetic registry'))
        e.update(changes)
        return e

    def run_report(self, entries=None, catalog=None, manifest=None, code=None):
        data = dict(manifest=manifest or dict(mapping_version='synthetic-v1'),
                    candidates=entries if entries is not None else [self.entry()],
                    target_catalog=catalog or {})
        php = (r'$x=json_decode($argv[2],true,512,JSON_THROW_ON_ERROR);'
               r'$r=\Mosa2\Phase3D\report($x);' +
               (code or r'echo \Mosa2\Phase3D\json($r);'))
        return subprocess.run(['php', '-r', 'require $argv[1];'+php, str(MODULE), json.dumps(data)],
                              check=True, capture_output=True, text=True).stdout

    def result(self, e):
        return json.loads(self.run_report([e]))['results'][0]

    def test_target_snapshot_missing_never_inserts(self):
        r = self.result(self.entry())
        self.assertTrue(r['transformation_valid'])
        self.assertEqual((r['action'], r['reason']), ('unresolved', 'target_snapshot_missing'))
        self.assertIsNone(r['resolved_asset_id'])
        self.assertIsNone(r['dedupe_key'])

    def test_canonical_order_and_fingerprint_deterministic(self):
        a, b = self.entry(), self.entry(sample_id='A2', source_reference='synthetic:2')
        b['row'] = dict(reversed(list(b['row'].items())))
        first = self.run_report([a, b])
        self.assertEqual(first, self.run_report([b, a]))
        r = json.loads(first)
        digest = r.pop('report_sha256')
        body = json.dumps(r, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        self.assertEqual(digest, hashlib.sha256(body.encode()).hexdigest())

    def test_phase3c_dedupe_exact_reuse_with_confirmed_catalog(self):
        e = self.entry()
        r = self.result(e)
        catalog = {r['proposed_route_key']: dict(proposed_asset_key=r['proposed_asset_key'],
                   proposed_source_key=r['proposed_source_key'], asset_id=7, source_id=8, route_id=9)}
        result = json.loads(self.run_report([e], catalog))['results'][0]
        row = dict(asset_id='7', source_id='8', route_id='9', **result['normalized_values'])
        expected = subprocess.run(['php', '-r',
            r'require $argv[1];echo bin2hex(\Mosa2\Phase3C\dedupeKey(json_decode($argv[2],true)));',
            str(ROOT/'scripts/phase3c/market_flow.php'), json.dumps(row)],
            capture_output=True, text=True, check=True).stdout
        self.assertEqual(result['dedupe_key'], expected)
        self.assertEqual(len(expected), 64)
        self.assertEqual(result['action'], 'unresolved')

    def test_identity_conflict_rejected(self):
        e = self.entry(); e['proof']['context_isin'] = 'GB0000000000'
        r = self.result(e)
        self.assertEqual((r['action'], r['reason']), ('reject', 'identity_conflict'))

    def test_invalid_isin_rejected(self):
        e = self.entry(); e['row']['isin'] = 'US0378331006'; e['proof'].pop('context_isin')
        self.assertIn('identifier_invalid', self.result(e)['reasons'])

    def test_ticker_alone_not_identity(self):
        e = self.entry(); e['row']['isin'] = None; e['proof'].pop('context_isin')
        self.assertIn('asset_identity_missing', self.result(e)['reasons'])

    def test_missing_route(self):
        e = self.entry(); e['proof'].pop('external_identity')
        self.assertIn('route_unresolved', self.result(e)['reasons'])

    def test_route_conflict_rejected(self):
        e = self.entry(); e['proof']['route_identity_conflict'] = True
        self.assertEqual(self.result(e)['action'], 'reject')

    def test_currency_venue_series_variant_are_route_identity(self):
        base = self.result(self.entry())['proposed_route_key']
        for key in ['currency', 'venue_key', 'series', 'quote_variant']:
            e = self.entry(); e['row'][key] = 'DIFFERENT'
            self.assertNotEqual(base, self.result(e)['proposed_route_key'])

    def test_timezone_ambiguous_and_missing_producer(self):
        for key in ['market_at_semantics', 'producer_reference']:
            e = self.entry(); e['proof'][key] = 'ambiguous' if key.endswith('semantics') else ''
            self.assertIn('timezone_ambiguous', self.result(e)['reasons'])

    def test_unknown_market_time(self):
        e = self.entry(); e['proof']['market_at_semantics'] = 'unknown'
        self.assertIn('market_time_unknown', self.result(e)['reasons'])

    def test_offset_epoch_and_already_utc(self):
        e = self.entry(); e['row']['quoted_at'] = '2026-01-01T13:00:00+01:00'
        e['proof']['market_at_semantics'] = 'explicit_offset'
        self.assertEqual(self.result(e)['normalized_values']['market_at'], '2026-01-01 12:00:00.000000')
        e['row']['quoted_at'] = '1767268800'; e['proof']['market_at_semantics'] = 'epoch_s'
        self.assertEqual(self.result(e)['normalized_values']['market_at'], '2026-01-01 12:00:00.000000')

    def test_gbx_without_scale_blocked(self):
        e = self.entry(); e['row']['currency'] = 'GBX'
        self.assertIn('unit_scale_required', self.result(e)['reasons'])
        e['proof']['gbx_scale'] = '0.01'
        r = self.result(e)
        self.assertTrue(r['transformation_valid'])
        self.assertEqual(r['normalized_values']['currency'], 'GBX')
        self.assertEqual(r['normalized_values']['price'], '10.2500000000')

    def test_xxx_or_missing_unit_blocked(self):
        for currency, unit, reason in [('XXX', 'points', 'unit_or_currency_missing'),
                                      ('EUR', 'unknown', 'unit_contract_unresolved')]:
            e = self.entry(); e['row']['currency'] = currency; e['proof']['unit_class'] = unit
            self.assertIn(reason, self.result(e)['reasons'])

    def test_derived_lineage_missing_blocks(self):
        e = self.entry(); e['row']['observation_kind'] = 'derived_quote'
        self.assertIn('derived_provenance_unresolved', self.result(e)['reasons'])

    def test_current_needs_explicit_route_not_legacy_selected(self):
        e = self.entry(); e['row']['is_selected'] = True
        r = self.result(e)
        self.assertEqual(r['current_reason'], 'current_route_unselected')
        e['proof'].update(selected_route_key=r['proposed_route_key'], selection_reference='synthetic approval')
        self.assertEqual(self.result(e)['current_relevant'], 'yes')

    def test_bar_missing_required_proofs(self):
        e = self.entry(target_type='bar'); e['row'].update(bar_open='10', bar_high='12',
                      bar_low='9', bar_close='11', bar_volume='2')
        r = self.result(e)
        self.assertTrue({'interval_unknown','bar_end_unknown','adjustment_unknown'} <= set(r['reasons']))
        self.assertFalse(r['transformation_valid'])
        e['proof'].update(interval_key='1m', interval_reference='synthetic interval',
                          ends_at='2026-01-01 12:01:00', end_reference='synthetic end',
                          adjustment_reference='synthetic unadjusted', revision_reference='synthetic frozen')
        self.assertTrue(self.result(e)['transformation_valid'])

    def test_point_not_invented_as_bar(self):
        e = self.entry(target_type='bar')
        self.assertIn('bar_values_invalid', self.result(e)['reasons'])

    def test_provider_statistics_not_target_columns(self):
        values = self.result(self.entry())['normalized_values']
        self.assertEqual(set(values), {'currency','market_at','observed_at','price','bid','ask','volume'})
        self.assertIsNone(values['volume'])

    def test_float_and_spread_invalid(self):
        for field, value in [('last_price', 10.25), ('ask_price', '8')]:
            e = self.entry(); e['row'][field] = value
            self.assertEqual(self.result(e)['action'], 'reject')

    def test_counts_and_limit(self):
        r = json.loads(self.run_report())['summary']
        self.assertEqual(r['target_candidates'], sum(r[k] for k in ['insert','duplicate','reject','unresolved']))
        self.assertEqual(r['source_objects'], 1)
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_report([self.entry(sample_id=f'A{i}') for i in range(31)])

    def test_no_io_network_database_or_clock_in_evaluator(self):
        source = MODULE.read_text()
        pure = source.split("if(PHP_SAPI==='cli'")[0]
        self.assertNotRegex(pure, r'\b(PDO|mysqli|curl_exec|file_put_contents|fopen|unlink|rename|exec|microtime|time)\s*\(')
        self.assertNotIn('INSERT INTO', source)
        self.assertNotIn('UPDATE ', source)
        self.assertNotIn('http://', source)

    def test_private_cli_two_runs_identical_and_input_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'synthetic.json'
            source.write_text(json.dumps(dict(manifest={}, candidates=[self.entry()])))
            before = source.read_bytes()
            command = ['php', str(MODULE), str(source)]
            a = subprocess.check_output(command); b = subprocess.check_output(command)
            self.assertEqual(a, b)
            self.assertEqual(source.read_bytes(), before)

    def test_secret_fields_refused(self):
        for field in ['password','auth_token','cookie','user_id']:
            with self.assertRaises(subprocess.CalledProcessError):
                self.run_report(manifest={field:'synthetic-forbidden-value'})

    def test_public_summary_drops_references_manifest_and_identity(self):
        e = self.entry(source_reference='synthetic-private-reference')
        public = self.run_report([e], manifest={'private_path':'synthetic-private-path'},
                   code=r'echo \Mosa2\Phase3D\json(\Mosa2\Phase3D\publicSummary($r));')
        self.assertNotIn('synthetic-private', public)
        self.assertNotIn('US0378331005', public)
        self.assertNotIn('results', json.loads(public))

    def test_migration_hashes_unchanged(self):
        for name, digest in [('0001_core_asset_identity.sql','9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd'),
                             ('0002_market_current_history.sql','205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee')]:
            self.assertEqual(hashlib.sha256((ROOT/'docs/database/migrations'/name).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
