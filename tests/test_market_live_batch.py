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


def call(manifests, outcomes=(), path_case=None, action=None, dogado=False, **extra):
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
                    outcomes=list(outcomes), action=action)|extra
        if dogado:
            from scripts import collector_dogado_pne as dogado_driver
            data["dogado_source"]=dogado_driver.php_source(release_root=str(ROOT),run_root=str(private),entry=False,launcher="dogado_batch_live.php")
        return json.loads(subprocess.check_output(['php',str(ROOT/'tests/market_live_batch_fixture.php')],
                          input=json.dumps(data).encode()))


class MarketLiveBatchTests(unittest.TestCase):
    def test_explicit_input_order_is_preserved(self):
        low, high = manifest(1), manifest(2)
        self.assertEqual(call([high, low])['calls'], [isin(2), isin(1)])

    def test_duplicate_identity_rejected_before_runner_even_with_different_key_order(self):
        a = manifest(1);b = copy.deepcopy(a);b['identity'] = dict(reversed(list(b['identity'].items())))
        result = call([a, b]);self.assertFalse(result['ok']);self.assertEqual(result['calls'], [])

    def test_only_existing_route_policy_allowed_before_first_runner(self):
        a, b = manifest(1), manifest(2);b['policy'] = 'ONBOARD_NEW_ROUTE'
        result = call([a, b], action='invalid_run')['batch']
        self.assertEqual(result['overall_status'], 'FAILED_BEFORE_FIRST_COMMIT')
        self.assertEqual(result['started_count'], 0);self.assertEqual(result['provider_requests'], 0)
        self.assertEqual(result['database_connections'], 0);self.assertEqual(result['not_started_count'], 2)

    def test_success_aggregates_and_reports_identity_without_private_paths(self):
        result = call([manifest(2), manifest(1)]);r = result['batch']
        self.assertEqual(r['overall_status'], 'COMPLETE')
        self.assertEqual([r[k] for k in ['started_count','completed_count','failed_count','not_started_count']], [2,2,0,0])
        self.assertEqual([r[k] for k in ['provider_requests','database_connections']], [2,4])
        self.assertEqual([x['source'] for x in r['item_results']], ['EXISTING_MATCH']*2)
        self.assertEqual([x['asset_identity'] for x in r['item_results']], [isin(2),isin(1)])
        r.pop('private_evidence');self.assertNotIn('private_root',json.dumps(r))

    def test_first_failure_keeps_second_not_started(self):
        r = call([manifest(2),manifest(1)], [dict(ok=False,committed=False)])['batch']
        self.assertEqual(r['overall_status'], 'FAILED_BEFORE_FIRST_COMMIT')
        self.assertEqual([x['status'] for x in r['item_results']], ['FAILED','NOT_STARTED'])
        self.assertEqual([r[k] for k in ['started_count','completed_count','failed_count','not_started_count']], [1,0,1,1])

    def test_second_failure_preserves_first_commit(self):
        r = call([manifest(1),manifest(2)], [{},dict(ok=False,committed=False)])['batch']
        self.assertEqual(r['overall_status'], 'PARTIAL_FAILED');self.assertEqual(r['completed_count'], 1)
        self.assertTrue(r['item_results'][0]['committed']);self.assertFalse(r['item_results'][1]['committed'])

    def test_failure_has_no_retry_and_sequence_has_no_overlap(self):
        r = call([manifest(3),manifest(2),manifest(1)], [{},dict(ok=False,committed=False)])
        self.assertEqual(r['calls'], [isin(3),isin(2)])
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

    def test_one_two_five_and_ten_assets_have_individual_commits_and_replays(self):
        for size in [1,2,5,10]:
            r=call([manifest(i) for i in range(size)])['batch']
            self.assertEqual(r['overall_status'],'COMPLETE');self.assertEqual(r['committed_count'],size)
            self.assertEqual(r['provider_requests'],size)
            self.assertTrue(all(x['replay']=='DUPLICATE_UNCHANGED' and x['committed'] for x in r['item_results']))

    def test_middle_failure_leaves_later_assets_unstarted_and_prior_commits(self):
        r=call([manifest(i) for i in range(5)],[{},{},dict(ok=False,committed=False,stage='transaction')])['batch']
        self.assertEqual(r['overall_status'],'PARTIAL_FAILED');self.assertEqual(r['committed_count'],2)
        self.assertEqual([x['status'] for x in r['item_results']],['COMPLETE','COMPLETE','FAILED','NOT_STARTED','NOT_STARTED'])
        self.assertEqual(r['item_results'][2]['failure_stage'],'transaction')
        self.assertFalse(r['item_results'][3]['provider_request_performed'])

    def test_first_readback_failure_after_commit_is_partial_failed(self):
        r=call([manifest(1),manifest(2)],[dict(ok=False,committed=True,stage='readback')])['batch']
        self.assertEqual(r['overall_status'],'PARTIAL_FAILED');self.assertEqual(r['committed_count'],1)

    def test_dogado_same_installed_coordinator_sizes_and_unknown_outcomes(self):
        for size in (1,2,5,10):
            r=call([manifest(i) for i in range(size)],dogado=True)['batch']
            self.assertEqual(r['overall_status'],'COMPLETE');self.assertEqual(r['requested_count'],size)
            self.assertEqual(r['insert_count'],size);self.assertEqual(r['provider_requests'],size)
        for failure in (dict(ok=False,committed=None,status='OUTCOME_UNKNOWN',stage='transaction'),
                        dict(throw=True)):
            r=call([manifest(1),manifest(2),manifest(3)],[{},failure],dogado=True)['batch']
            self.assertEqual(r['overall_status'],'OUTCOME_UNKNOWN')
            self.assertTrue(r['item_results'][0]['committed'])
            self.assertEqual(r['item_results'][1]['status'],'OUTCOME_UNKNOWN')
            self.assertEqual(r['item_results'][2]['status'],'NOT_STARTED')
            self.assertEqual(r['started_count'],2)

    def test_dogado_writer_provider_readback_failures_stop_and_preserve_commits(self):
        for stage,committed in (('provider',False),('transaction',False),('readback',True)):
            r=call([manifest(1),manifest(2),manifest(3)],
                [{},dict(ok=False,committed=committed,stage=stage,failure_code='collector_check_failed')],dogado=True)['batch']
            self.assertEqual(r['overall_status'],'PARTIAL_FAILED')
            self.assertEqual(r['committed_count'],1+int(committed))
            self.assertEqual(r['item_results'][1]['failure_stage'],stage)
            self.assertEqual(r['item_results'][1]['failure_code'],'collector_check_failed')
            self.assertEqual(r['item_results'][2]['status'],'NOT_STARTED')
        r=call([manifest(1)],[dict(writer='DUPLICATE_UNCHANGED')],dogado=True)['batch']
        self.assertEqual((r['insert_count'],r['duplicate_unchanged_count']),(0,1))

    def test_dogado_complete_qualification_equity_route_and_identity_before_runner(self):
        import test_market_onboarding as o
        s,m=o.MarketOnboardingTests().existing_live()
        for label in ('valid','duplicate','etf','missing_route','missing_asset','unit_drift'):
            state=copy.deepcopy(s);selection=[m['instrument']]
            if label=='duplicate':selection*=2
            if label=='etf':state['m2_assets'][0]['asset_class']='etf'
            if label=='missing_route':state['m2_asset_source_routes']=[]
            if label=='missing_asset':state['m2_asset_identifiers']=[]
            if label=='unit_drift':state['m2_asset_source_routes'][0]['quote_unit_version']='2'
            r=call([manifest(1)],action='qualify',dogado=True,state=state,selection=selection,qualified_manifests={m['instrument']:m})
            self.assertEqual(r['ok'],label=='valid',(label,r));self.assertEqual(r['calls'],[])
        r=call([manifest(1),manifest(1)],dogado=True)
        self.assertFalse(r['ok']);self.assertEqual(r['calls'],[])


    def test_dogado_outer_exception_after_coordinator_entry_is_always_unknown(self):
        r=call([manifest(1)],action='outcome_guard',dogado=True)
        self.assertEqual(r,dict(before='FAILED_BEFORE_FIRST_COMMIT',after='OUTCOME_UNKNOWN'))
