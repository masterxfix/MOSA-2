"""Synthetic catalog/evidence/replay checks; no DB, credentials or real samples."""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Phase3DImportTests(unittest.TestCase):
    def scenario(self, name):
        out = subprocess.check_output(['php', str(ROOT/'tests/phase3d_import_fixture.php')],
                                      input=json.dumps({'scenario':name}).encode())
        return json.loads(out)

    def test_explicit_equity_and_stock(self):
        for case in ['evidence_equity','evidence_stock']:
            r=self.scenario(case)
            self.assertTrue(r['ok']); self.assertEqual(r['result']['asset_class'],'equity')
            self.assertIsNone(r['result']['base_currency'])

    def test_exact_etf_reference(self):
        r=self.scenario('evidence_etf')
        self.assertTrue(r['ok']); self.assertEqual(r['result']['asset_class'],'etf')

    def test_missing_name_no_ticker_or_isin_default(self):
        for case in ['evidence_missing_name','evidence_ticker_name']:
            self.assertFalse(self.scenario(case)['ok'])

    def test_missing_or_unknown_type_no_default(self):
        for case in ['evidence_missing_type','evidence_unknown_type']:
            self.assertFalse(self.scenario(case)['ok'])

    def test_conflicting_names_and_types(self):
        for case in ['evidence_name_conflict','evidence_type_conflict']:
            self.assertFalse(self.scenario(case)['ok'])

    def test_cross_store_asset_and_user_identity(self):
        for case in ['evidence_asset_mismatch','evidence_user_mismatch']:
            self.assertFalse(self.scenario(case)['ok'])

    def test_exact_three_and_one_native_nok(self):
        for case in ['bad_count','bad_currency']:
            self.assertFalse(self.scenario(case)['ok'])

    def test_no_base_currency_from_quote(self):
        self.assertFalse(self.scenario('bad_base_currency')['ok'])

    def test_asset_evidence_required(self):
        self.assertFalse(self.scenario('missing_asset_evidence')['ok'])

    def test_manifest_deterministic(self):
        self.assertTrue(self.scenario('determinism')['same'])

    def test_catalog_and_checkpoint_replay_changes_nothing(self):
        r=self.scenario('replay')
        self.assertTrue(r['ok']); self.assertTrue(r['facts_same'])
        self.assertEqual(sum(r['second']['new'].values()),0)
        self.assertEqual(r['counts']['m2_entities'],2)
        self.assertEqual(r['counts']['m2_assets'],2)
        self.assertEqual(r['counts']['m2_asset_identifiers'],2)
        self.assertEqual(r['counts']['m2_sources'],2)
        self.assertEqual(r['counts']['m2_asset_source_routes'],3)
        self.assertEqual(r['counts']['m2_sync_checkpoints'],2)

    def test_three_observations_same_phase3c_dedupe(self):
        r=self.scenario('replay')
        self.assertTrue(r['dedupe_same'])
        self.assertEqual(r['counts']['m2_market_observations'],3)
        self.assertEqual([e['action'] for e in r['second']['bindings']],['duplicate']*3)
        for e in r['first']['bindings']:
            self.assertEqual(len(e['dedupe_hex']),64)
            self.assertTrue(e['canonical'].startswith('mosa2-observation-v1\n'))

    def test_each_catalog_conflict_fails_closed(self):
        for kind in ['source','asset','identifier','route','checkpoint','dedupe']:
            self.assertFalse(self.scenario(kind+'_conflict')['ok'],kind)

    def test_only_seven_allowed_tables_written(self):
        tables=set(self.scenario('replay')['tables'])
        self.assertEqual(tables,{'m2_entities','m2_assets','m2_asset_identifiers','m2_sources',
                                'm2_asset_source_routes','m2_market_observations','m2_sync_checkpoints'})
        self.assertNotIn('m2_market_current',tables)
        self.assertNotIn('m2_market_bars',tables)

    def test_no_update_delete_ddl_or_duplicate_suppression(self):
        source=(ROOT/'scripts/phase3d/import_sample.php').read_text()
        self.assertNotRegex(source,r"(?:UPDATE|DELETE FROM|REPLACE INTO|TRUNCATE|ALTER TABLE|CREATE TABLE|DROP TABLE) ")
        self.assertNotIn('catch(PDOException',source)
        self.assertIn("$p->beginTransaction()",source)
        self.assertIn("$p->rollBack()",source)
        self.assertIn("fopen($root.'/started.lock','x')",source)
        self.assertIn("$r['commit_attempted']=true",source)

    def test_replay_uses_actual_generated_ids(self):
        r=self.scenario('replay')
        self.assertTrue(all(int(e['observation']['asset_id'])>1000 for e in r['first']['bindings']))

    def test_public_import_evidence_has_no_real_identifiers(self):
        for name in ['PHASE3D_TEST_IMPORT.md','PHASE3D_TEST_IMPORT_RESULTS.md',
                     'PHASE3D_MARKET_MIGRATION.md','PHASE3D_NEXT_BATCH.md',
                     'PHASE3D_BATCH2_IMPORT_RESULTS.md','PHASE3D_BATCH3_IMPORT_RESULTS.md',
                     'PHASE3D_BATCH3_PLAN.md']:
            text=(ROOT/'docs/database'/name).read_text(encoding='utf-8')
            self.assertNotRegex(text,r'\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b')
            self.assertNotRegex(text,r'fixlab_market_observations:[0-9]+|object_[a-f0-9]{24}')
            self.assertNotRegex(text,r'[A-Z]:[\\/]|/var/www/|h29077')


if __name__=='__main__': unittest.main()
