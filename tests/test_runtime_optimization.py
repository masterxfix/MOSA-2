"""Regression comparison of previous metadata SQL and bundled runtime; no network."""
import copy
import json
import unittest
import test_market_runtime as runtime

class ReferenceRuntimeTests(runtime.RuntimeTests):
    """Run the existing integrity suite through the previous metadata reader."""
    def call(self, **extra):
        return super().call(**(extra | dict(reference=True)))

class OptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime.RuntimeTests.setUpClass.__func__(cls)

    call = runtime.RuntimeTests.call
    batch_inputs = runtime.RuntimeTests.batch_inputs

    def pair(self, **extra):
        return self.call(reference=True, **extra), self.call(**extra)

    def test_offline_one_two_five_state_results_rows_sql_and_pdo(self):
        for size in (1, 2, 5):
            old, new = self.pair(action='states', **self.batch_inputs(size))
            self.assertEqual(len(new['reports']), size)
            totals = []
            for before, after in zip(old['reports'], new['reports']):
                self.assertEqual(before['state'], after['state'])
                for b, a in zip(before['phases'], after['phases']):
                    self.assertEqual(b['returned_rows'], a['returned_rows'])
                    self.assertEqual(b['pdo_calls'], 47)
                    self.assertEqual(a['pdo_calls'], 41)
                    self.assertEqual(sum(b['by_operation'][k]['calls'] for k in ('query','execute')), 17)
                    self.assertEqual(sum(a['by_operation'][k]['calls'] for k in ('query','execute')), 14)
                totals.append(dict(sql_before=68, sql_after=56, pdo_before=188, pdo_after=164,
                                   rows_before=sum(p['returned_rows'] for p in before['phases']),
                                   rows_after=sum(p['returned_rows'] for p in after['phases'])))
            self.assertEqual(new['providers'], 0)
            self.assertEqual(new['state']['m2_market_observations'], [])
            print('OFFLINE_RUNTIME_COMPARISON '+json.dumps(dict(assets=size, per_asset=totals)))

    def test_full_runtime_one_two_five_identical_decisions_and_writes(self):
        for size in (1, 2, 5):
            old, new = self.pair(**self.batch_inputs(size))
            self.assertEqual(old['reports'], new['reports'])
            self.assertEqual(old['events'], new['events'])
            for table in old['state']:
                if table == 'm2_market_observations':
                    strip = lambda rows: [{k:v for k,v in r.items() if k!='created_at'} for r in rows]
                    self.assertEqual(strip(old['state'][table]), strip(new['state'][table]))
                else:
                    self.assertEqual(old['state'][table], new['state'][table])
            writes = lambda r: [q for q in r['queries'] if q.startswith(('INSERT ', 'UPDATE ', 'DELETE ', 'REPLACE ', 'ALTER '))]
            self.assertEqual(writes(old), writes(new))
            self.assertEqual(len(writes(new)), size)
            self.assertEqual(new['state']['m2_market_current'], [])
            self.assertEqual(new['state']['m2_market_bars'], [])

    def test_insert_duplicate_conflict_corrupt_observation_decisions(self):
        old, new = self.pair(runs=2)
        self.assertEqual(old['reports'], new['reports'])
        self.assertEqual([r['writer'] for r in new['reports']], ['INSERT','DUPLICATE_UNCHANGED'])
        fact=new['state']['m2_market_observations'][0]
        for altered in (fact | dict(price='999.0000000000'), fact | dict(route_id='88')):
            before, after=self.pair(observations=[altered])
            self.assertFalse(after['reports'][0]['ok'])
            self.assertEqual(before['reports'], after['reports'])
            self.assertEqual(before['state'], after['state'])

    def test_ledger_unit_route_schema_and_index_drift_between_checkpoints(self):
        for fault in ('ledger_drift','unit_drift','route_drift','schema_drift','index_drift',
                      'late_ledger','late_unit','late_route','late_index'):
            with self.subTest(fault=fault):
                old, new=self.pair(fault=fault)
                for r in (old, new):
                    self.assertFalse(r['reports'][0]['ok'])
                    self.assertFalse(r['reports'][0]['committed'])
                    self.assertEqual(r['state']['m2_market_observations'], [])
                    if fault.startswith('late_'):
                        self.assertTrue(r['reports'][0]['rollback'])
                self.assertEqual(old['reports'], new['reports'])

    def test_independent_readback_never_reuses_metadata_or_observation(self):
        for fault in ('independent_route','independent_observation'):
            old, new=self.pair(fault=fault)
            self.assertEqual(old['reports'], new['reports'])
            self.assertTrue(new['reports'][0]['committed'])
            self.assertFalse(new['reports'][0]['ok'])
            self.assertEqual(new['reports'][0]['stage'], 'readback')
            self.assertEqual(new['reports'][0]['database_connections'], 2)

    def test_no_fallback_on_metadata_failure_or_missing_unique_index(self):
        for fault in ('metadata_error','bad_index'):
            result=self.call(fault=fault)
            self.assertFalse(result['reports'][0]['ok'])
            self.assertFalse(result['reports'][0]['committed'])
            self.assertEqual(result['providers'], 0)
            self.assertEqual(result['state']['m2_market_observations'], [])
            self.assertFalse(any(q.startswith('SHOW INDEX') for q in result['queries']))

    def test_rollback_partial_failure_and_stop_are_identical(self):
        old, new=self.pair(fault='replay')
        self.assertEqual(old['reports'], new['reports'])
        self.assertTrue(new['reports'][0]['rollback'])
        self.assertEqual(new['reports'][0]['readback'], 'PASS')
        old, new=self.pair(**self.batch_inputs(5), batch_fault_index=2)
        self.assertEqual(old['reports'], new['reports'])
        self.assertEqual(len(new['state']['m2_market_observations']), 2)
        self.assertEqual(new['providers'], 3)
        self.assertEqual([r['status'] for r in new['reports'][0]['item_results']],
                         ['COMPLETE','COMPLETE','FAILED','NOT_STARTED','NOT_STARTED'])

if __name__=='__main__':
    unittest.main()
