"""Batch coordination only: synthetic manifests, filesystem, fake runners; no DB/network."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def isin(serial):
    stem = 'ZZ'+f'{serial:09d}'
    for digit in '0123456789':
        value = stem+digit
        expanded = ''.join(c if c.isdigit() else str(ord(c)-55) for c in value)
        if sum((int(c)* (2 if i % 2 else 1))//10 + (int(c)*(2 if i % 2 else 1)) % 10
               for i, c in enumerate(reversed(expanded))) % 10 == 0:
            return value


def manifest(serial):
    value = isin(serial)
    return dict(policy='USE_EXISTING_ROUTE', identity=dict(canonical_name=f'Synthetic {100-serial}',
        display_name=f'Synthetic {100-serial}', asset_class='equity', identifier_type='isin',
        identifier_value=value, normalized_value=value, scope_key='', is_primary=1))


def call(manifests, outcomes=(), path_case=None, action=None):
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary).resolve();private = base/'private';web = base/'web'
        private.mkdir();web.mkdir();entries = []
        for i, item in enumerate(manifests):
            folder = private/f'item-{i}';folder.mkdir()
            (folder/'live-manifest.json').write_text(json.dumps(item), encoding='utf-8')
            entries.append(dict(private_root=str(folder)))
        if path_case == 'duplicate':
            entries[1] = entries[0]
        if path_case == 'outside':
            entries[0]['private_root'] = str(base)
        if path_case == 'web':
            private = web
        data = dict(private_root=str(private), public_root=str(web), entries=entries,
                    outcomes=list(outcomes), action=action)
        return json.loads(subprocess.check_output(['php',str(ROOT/'tests/market_live_batch_fixture.php')],
                          input=json.dumps(data).encode()))


class MarketLiveBatchTests(unittest.TestCase):
    def test_identifier_order_overrides_input_and_name(self):
        low, high = manifest(1), manifest(2)
        self.assertEqual(call([high, low])['calls'], [isin(1), isin(2)])

    def test_duplicate_identity_rejected_before_runner_even_with_different_key_order(self):
        a = manifest(1);b = copy.deepcopy(a);b['identity'] = dict(reversed(list(b['identity'].items())))
        result = call([a, b]);self.assertFalse(result['ok']);self.assertEqual(result['calls'], [])

    def test_only_existing_route_policy_allowed_before_first_runner(self):
        a, b = manifest(1), manifest(2);b['policy'] = 'ONBOARD_NEW_ROUTE'
        result = call([a, b], action='invalid_run')['batch']
        self.assertEqual(result['overall_status'], 'FAILED_BEFORE_FIRST_ITEM')
        self.assertEqual(result['started_count'], 0);self.assertEqual(result['provider_requests'], 0)
        self.assertEqual(result['database_connections'], 0);self.assertEqual(result['not_started_count'], 2)

    def test_success_aggregates_and_returns_public_results_without_identity(self):
        result = call([manifest(2), manifest(1)]);r = result['batch']
        self.assertEqual(r['overall_status'], 'COMPLETE')
        self.assertEqual([r[k] for k in ['started_count','completed_count','failed_count','not_started_count']], [2,2,0,0])
        self.assertEqual([r[k] for k in ['provider_requests','database_connections']], [2,4])
        self.assertEqual([x['source'] for x in r['item_results']], ['EXISTING_MATCH']*2)
        r.pop('private_evidence');self.assertNotIn(isin(1), json.dumps(r));self.assertNotIn('private_root',json.dumps(r))

    def test_first_failure_keeps_second_not_started(self):
        r = call([manifest(2),manifest(1)], [dict(ok=False,committed=False)])['batch']
        self.assertEqual(r['overall_status'], 'PARTIAL')
        self.assertEqual([x['status'] for x in r['item_results']], ['FAILED','NOT_STARTED'])
        self.assertEqual([r[k] for k in ['started_count','completed_count','failed_count','not_started_count']], [1,0,1,1])

    def test_second_failure_preserves_first_commit(self):
        r = call([manifest(1),manifest(2)], [{},dict(ok=False,committed=False)])['batch']
        self.assertEqual(r['overall_status'], 'PARTIAL');self.assertEqual(r['completed_count'], 1)
        self.assertTrue(r['item_results'][0]['committed']);self.assertFalse(r['item_results'][1]['committed'])

    def test_failure_has_no_retry_and_sequence_has_no_overlap(self):
        r = call([manifest(3),manifest(2),manifest(1)], [{},dict(ok=False,committed=False)])
        self.assertEqual(r['calls'], [isin(1),isin(2)])
        self.assertEqual(r['events'], ['start:0','finish:0','start:1','finish:1'])
        self.assertEqual(r['batch']['not_started_count'], 1)
        thrown = call([manifest(1),manifest(2)], [dict(throw=True)])
        self.assertEqual(thrown['calls'], [isin(1)]);self.assertIsNone(thrown['batch']['provider_requests'])

    def test_private_folders_are_unique_contained_and_outside_webroot(self):
        for case in ['duplicate','outside','web']:
            r = call([manifest(1),manifest(2)], path_case=case)
            self.assertFalse(r['ok']);self.assertEqual(r['calls'], [])

    def test_existing_runner_only_no_business_duplication_parallelism_or_asset_literals(self):
        text = (ROOT/'scripts/market_collector/live_batch.php').read_text(encoding='utf-8')
        self.assertEqual(text.count('\\Mosa2\\MarketLive\\run('), 1)
        for forbidden in ['completePlan(', 'compareDelta(', 'bridge(', 'PDO', 'INSERT INTO',
                          'pcntl_', 'Thread', 'Worker', 'curl_multi', 'sleep(']:
            self.assertNotIn(forbidden, text)
        self.assertNotRegex(text, r'\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b')
        self.assertIn('is_link(', text)

    def test_size_and_global_identifier_validation_before_any_runner(self):
        bad = manifest(1);bad['identity']['scope_key'] = 'local'
        invalid = manifest(1);invalid['identity']['normalized_value'] = 'invalid'
        for items in [[],[manifest(i) for i in range(11)],[bad],[invalid]]:
            r = call(items);self.assertFalse(r['ok']);self.assertEqual(r['calls'], [])
        self.assertEqual(call([manifest(1)])['batch']['overall_status'], 'COMPLETE')
