"""Existing-baseline and general stream regression tests; purely synthetic."""
import json
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
class BatchImportTests(unittest.TestCase):
    @classmethod
    def scenario(cls,name,**kwargs):
        return json.loads(subprocess.check_output(['php',str(ROOT/'tests/phase3d_batch_fixture.php')],input=json.dumps(dict(scenario=name,**kwargs)).encode()))
    @classmethod
    def setUpClass(cls):
        cls.r=cls.scenario('replay')
        if not cls.r['ok']:raise AssertionError(cls.r)
    def test_general_manifest_accepts_one_to_three_only(self):
        for count in range(5):
            self.assertEqual(self.scenario('size',count=count)['ok'],1 <= count <= 3)
    def test_independent_two_after_both_prior_packages(self):
        r=self.scenario('independent_two');self.assertTrue(r['ok'],r)
        self.assertEqual(r['first']['new'],dict(m2_entities=2,m2_assets=2,m2_asset_identifiers=2,m2_sources=1,m2_asset_source_routes=2,m2_market_observations=2,m2_sync_checkpoints=1))
        for t,n in dict(m2_entities=7,m2_assets=7,m2_asset_identifiers=7,m2_sources=4,m2_asset_source_routes=8,m2_market_observations=8,m2_sync_checkpoints=5,m2_market_current=0,m2_market_bars=0).items():self.assertEqual(r['counts'][t],n)
        self.assertEqual(r['baseline_checkpoint_count'],4);self.assertTrue(r['baseline_checkpoints_same']);self.assertTrue(r['baseline_preserved']);self.assertTrue(r['watermarks_correct'])
        self.assertEqual(sum(r['second']['new'].values()),0);self.assertTrue(r['same'])
        self.assertEqual([b['action'] for b in r['second']['bindings']],['duplicate']*2)
        for a,b in zip(r['first']['bindings'],r['second']['bindings']):
            self.assertGreater(int(a['observation']['asset_id']),1005)
            self.assertEqual(a['dedupe_hex'],b['dedupe_hex']);self.assertEqual(len(a['dedupe_hex']),64)
            self.assertTrue(a['canonical'].startswith('mosa2-observation-v1\n'))
    def test_existing_baseline_and_exact_new_catalog(self):
        expected=dict(m2_entities=3,m2_assets=3,m2_asset_identifiers=3,m2_sources=1,m2_asset_source_routes=3,m2_market_observations=3,m2_sync_checkpoints=2)
        self.assertEqual(self.r['first']['new'],expected)
        for table,n in dict(m2_entities=5,m2_assets=5,m2_asset_identifiers=5,m2_sources=3,m2_asset_source_routes=6,m2_market_observations=6,m2_sync_checkpoints=4).items():
            self.assertEqual(self.r['counts'][table],n)
    def test_baseline_nested_key_order_is_not_a_data_change(self):
        self.assertTrue(self.scenario('baseline_key_order')['ok'])
    def compare_evidence(self, actual, expected):
        return json.loads(subprocess.check_output(['php',str(ROOT/'tests/phase3d_batch_fixture.php')],input=json.dumps(dict(scenario='comparison',actual=actual,expected=expected)).encode()))['ok']
    def test_recursive_map_key_order_equal(self):
        self.assertTrue(self.compare_evidence({'a':1,'b':{'x':2,'y':3}}, {'b':{'y':3,'x':2},'a':1}))
    def test_nested_added_missing_or_changed_keys_fail(self):
        a={'a':1,'b':{'x':2,'y':3}}
        for b in [{'a':1,'b':{'x':2,'y':4}}, {'a':1,'b':{'x':2,'y':3,'z':4}}, {'a':1,'b':{'x':2}}]:
            self.assertFalse(self.compare_evidence(a,b))
    def test_list_order_and_scalar_types_remain_strict(self):
        for a,b in [([1,2,3],[3,2,1]), ({'v':1},{'v':'1'}), ({'v':1},{'v':1.0}), ({'v':True},{'v':1}), ({'v':None},{'v':''})]:
            self.assertFalse(self.compare_evidence(a,b))
    def test_extra_or_changed_baseline_blocks(self):
        for case in ['extra_baseline','changed_baseline']:self.assertFalse(self.scenario(case)['ok'])
    def test_catalog_conflict_and_wrong_stream_block(self):
        for case in ['catalog_conflict','stream_conflict','too_many']:self.assertFalse(self.scenario(case)['ok'])
    def test_final_dedupe_uses_generated_real_ids(self):
        for a,b in zip(self.r['first']['bindings'],self.r['second']['bindings']):
            self.assertEqual(a['dedupe_hex'],b['dedupe_hex']);self.assertEqual(len(a['dedupe_hex']),64)
            self.assertGreater(int(a['observation']['asset_id']),1002)
            self.assertTrue(a['canonical'].startswith('mosa2-observation-v1\n'))
    def test_replay_zero_everywhere_and_values_unchanged(self):
        self.assertEqual(sum(self.r['second']['new'].values()),0);self.assertTrue(self.r['same'])
        self.assertEqual([r['action'] for r in self.r['second']['bindings']],['duplicate']*3)
    def test_prior_package_and_checkpoint_times_unchanged(self):
        self.assertTrue(self.r['baseline_preserved']);self.assertTrue(self.r['legacy_checkpoints_same'])
    def test_two_general_stream_checkpoints_and_correct_watermarks(self):
        cps=self.r['migration_checkpoints'];self.assertEqual(len(cps),2);self.assertTrue(self.r['watermarks_correct'])
        self.assertTrue(all(c['stream_key']=='phase3d_market_migration_v1' for c in cps))
        self.assertEqual(len({c['cursor_value'] for c in cps}),1)
    def test_current_bars_and_foreign_tables_remain_empty(self):
        for t in ['m2_market_current','m2_market_bars','m2_relationships','m2_files','m2_events','m2_jobs','m2_job_runs','m2_module_state']:self.assertEqual(self.r['counts'][t],0)
    def test_no_update_or_foreign_write_capability(self):
        code=(ROOT/'scripts/phase3d/import_sample.php').read_text(encoding='utf-8')
        self.assertNotRegex(code,r'(?:UPDATE|DELETE FROM|REPLACE INTO|ALTER TABLE|CREATE TABLE|DROP TABLE) ')
        self.assertEqual(len(self.r['tables']),7)
        self.assertIn("same(hash_file('sha256',$root.'/baseline.json'),$m['baseline_sha256']",code)
    def test_deterministic_general_manifest(self):self.assertTrue(self.scenario('determinism')['same'])
if __name__=='__main__':unittest.main()
