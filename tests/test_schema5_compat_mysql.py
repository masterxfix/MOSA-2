"""Explicit schema selection and existing Current transaction in the ephemeral MySQL8 service."""
import json, subprocess, sys, unittest
import test_migration5_mysql as fixtures
from test_collector_persistence_mysql import ENABLED
from scripts import collector_migration5 as m

@unittest.skipUnless(ENABLED, 'temporary GitHub MySQL8 service only')
class CompatibilityMySQLTests(unittest.TestCase):
    # Reuse the existing synthetic schema/seed builder; no second DB connection route.
    sql=fixtures.Migration5MySQLTests.sql
    insert=fixtures.Migration5MySQLTests.insert
    seed=fixtures.Migration5MySQLTests.seed
    reset=fixtures.Migration5MySQLTests.reset
    migrate=fixtures.Migration5MySQLTests.migrate
    ledger5=fixtures.Migration5MySQLTests.ledger5
    baseline_rows=fixtures.Migration5MySQLTests.baseline_rows
    def setUp(self): self.reset()
    def probe(self, operation='contract', version=None, **extra):
        config={} if version is None else dict(state_contract=dict(schema_version=version))
        routes=[str(r['id']) for r in self.sql('SELECT id FROM m2_asset_source_routes ORDER BY id')]
        p=subprocess.run(['php',str(m.ROOT/'tests/schema5_compat_mysql.php')],
            input=json.dumps(dict(operation=operation,config=config,routes=routes,python=sys.executable,**extra)),
            capture_output=True,text=True,check=True,timeout=60)
        self.assertEqual(p.stderr,'');result=json.loads(p.stdout)
        self.assertEqual(result['provider_requests'],0);return result
    def test_transition_matrix_and_real_current_readback_replay(self):
        old=self.baseline_rows()
        for version in (None,4):
            self.assertEqual(self.probe(version=version)['result'],dict(tables=17,ledger=4))
            r=self.probe('current',version,allow_disabled=True)
            self.assertTrue(r['ok'],r);self.assertEqual(r['result']['decisions'],['UNCHANGED']*5)
            self.assertEqual(r['result']['readback'],'PASS');self.assertTrue(r['result']['unchanged'])
        self.assertFalse(self.probe(version=5)['ok'])
        self.migrate()
        for version in (None,4):
            self.assertEqual(self.probe(version=version)['code'],'table_set')
        self.assertEqual(self.probe(version=5)['result'],dict(tables=21,ledger=5))
        r=self.probe('collector',5);self.assertTrue(r['ok'],r)
        self.assertEqual(r['result']['failure'],'schema5_collector_locked')
        self.assertFalse(r['result']['committed']);self.assertEqual(r['result']['provider_requests'],0)
        r=self.probe('current',5,allow_disabled=True);self.assertTrue(r['ok'],r)
        self.assertEqual(r['result']['decisions'],['UNCHANGED']*5)
        self.assertEqual(r['result']['replay'],'UNCHANGED');self.assertTrue(r['result']['unchanged'])
        self.assertEqual(self.baseline_rows(),old)
    def test_disabled_route_never_grants_current_projection(self):
        for version in (4,5):
            if version==5:self.migrate()
            before=self.baseline_rows();r=self.probe('current',version)
            self.assertFalse(r['ok'],r);self.assertIn('current_route_not_approved',r['code'])
            self.assertEqual(self.baseline_rows(),before)
    def test_missing_tables_ledger_and_checksum_fail_closed(self):
        changes=[('DELETE FROM m2_schema_migrations WHERE version=5','ledger_versions'),
            ("UPDATE m2_schema_migrations SET checksum=UNHEX(REPEAT('00',32)) WHERE version=5",'ledger_checksum'),
            ("UPDATE m2_schema_migrations SET migration_key='wrong' WHERE version=5",'schema5_ledger_keys'),
            ('DROP TABLE m2_collector_requests','table_set')]
        for sql,code in changes:
            with self.subTest(code=code):
                self.reset();self.migrate();self.sql(sql)
                self.assertEqual(self.probe(version=5)['code'],code)
    def test_every_locked_anchor_is_enforced(self):
        for sql,code in [
            ('UPDATE m2_jobs SET enabled=1','schema5_job'),
            ("UPDATE m2_jobs SET handler_key='other'",'schema5_job'),
            ("UPDATE m2_module_state SET status='ENABLED'",'schema5_module'),
            ('UPDATE m2_module_state SET schema_version=4','schema5_module'),
            ('UPDATE m2_collector_state SET stop_latched=0','schema5_state'),
            ("UPDATE m2_collector_state SET error_code='OTHER'",'schema5_state')]:
            with self.subTest(sql=sql):
                self.reset();self.migrate();self.sql(sql)
                self.assertEqual(self.probe(version=5)['code'],code)
    def test_corrupt_observation_provenance_blocks_current_and_preserves_prices(self):
        self.migrate();self.sql('UPDATE m2_market_current SET observation_dedupe_key=UNHEX(REPEAT(\'00\',32)) WHERE asset_id=1100')
        before=self.baseline_rows();r=self.probe('current',5,allow_disabled=True)
        self.assertFalse(r['ok'],r);self.assertEqual(self.baseline_rows(),before)

if __name__=='__main__':unittest.main()
