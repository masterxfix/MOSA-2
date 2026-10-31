"""Additional schema6 compatibility only; existing guarded disposable MySQL8 fixture."""
import hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
import test_migration5_mysql as f
from test_collector_persistence_mysql import ENABLED
from scripts import collector_migration5 as m

@unittest.skipUnless(ENABLED,'temporary GitHub MySQL8 service only')
class Schema6MySQLTests(unittest.TestCase):
    sql=f.Migration5MySQLTests.sql
    insert=f.Migration5MySQLTests.insert
    seed=f.Migration5MySQLTests.seed
    reset=f.Migration5MySQLTests.reset
    migrate=f.Migration5MySQLTests.migrate
    ledger5=f.Migration5MySQLTests.ledger5
    baseline_rows=f.Migration5MySQLTests.baseline_rows
    fixture=f.Migration5MySQLTests.fixture
    def setUp(self):self.reset()
    def probe(self,operation='contract',version=6,**extra):
        routes=[str(r['id']) for r in self.sql('SELECT id FROM m2_asset_source_routes ORDER BY id')]
        p=subprocess.run(['php',str(m.ROOT/'tests/schema5_compat_mysql.php')],
            input=json.dumps(dict(operation=operation,config=dict(state_contract=dict(schema_version=version)),
                routes=routes,python=sys.executable,**extra)),capture_output=True,text=True,check=True,timeout=90)
        self.assertEqual(p.stderr,'');r=json.loads(p.stdout);self.assertEqual(r['provider_requests'],0);return r
    def ledger6(self):
        path=next((m.ROOT/'docs/database/migrations').glob('0006_*.sql'))
        self.sql("INSERT INTO m2_schema_migrations VALUES (6,'0006_fundamentals_and_payload_provenance',%s,UTC_TIMESTAMP(6))",
            (hashlib.sha256(path.read_bytes()).digest(),))
    def extend6(self,ledger=True):
        path=next((m.ROOT/'docs/database/migrations').glob('0006_*.sql'))
        text='\n'.join(l for l in path.read_text().splitlines() if not l.lstrip().startswith('--'))
        for statement in text.split(';'):
            if statement.strip():self.sql(statement)
        if ledger:self.ledger6()
    def ready6(self):self.migrate();self.extend6()
    def test_transition_six_checksums_structure_readers_current_replay_and_no_provider(self):
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (m.ROOT/'docs/database/migrations').glob('000[1-6]_*.sql')}
        old=self.baseline_rows();web=self.fixture('current')
        self.assertEqual(len(web['current']['items']),5);self.assertEqual(len(web['observations']['items']),5)
        self.assertEqual(self.probe(version=4)['result'],dict(tables=17,ledger=4))
        self.assertFalse(self.probe()['ok'])
        self.migrate()
        self.assertEqual(self.probe(version=5)['result'],dict(tables=21,ledger=5))
        self.assertFalse(self.probe()['ok'])
        self.extend6(ledger=False);self.assertEqual(self.probe()['code'],'ledger_versions')
        self.ledger6()
        self.assertEqual(self.probe()['result'],dict(tables=26,ledger=6))
        for v in (4,5):self.assertEqual(self.probe(version=v)['code'],'table_set')
        self.assertEqual(self.baseline_rows(),old);self.assertEqual(self.fixture('current'),web)
        result=self.probe('current',allow_disabled=True);self.assertTrue(result['ok'],result)
        self.assertEqual(result['result']['decisions'],['UNCHANGED']*5)
        self.assertEqual(result['result']['readback'],'PASS');self.assertEqual(result['result']['replay'],'UNCHANGED')
        self.assertTrue(result['result']['unchanged'])
        denied=self.probe('current');self.assertFalse(denied['ok']);self.assertIn('current_route_not_approved',denied['code'])
        collector=self.probe('collector');self.assertTrue(collector['ok'],collector)
        self.assertEqual(collector['result']['failure'],'schema6_collector_locked')
        self.assertFalse(collector['result']['committed'])
        for table in ('m2_provider_fetches','m2_fundamental_metrics','m2_fundamental_units','m2_fundamental_observations','m2_fundamental_current'):
            self.assertEqual(self.sql('SELECT COUNT(*) AS n FROM '+table)[0]['n'],0)
        self.assertEqual(hashes,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (m.ROOT/'docs/database/migrations').glob('000[1-6]_*.sql')})
        print(json.dumps(dict(status='SCHEMA6_COMPATIBILITY_PASS',mysql_version=self.sql('SELECT VERSION() AS v')[0]['v'],
            tables=26,ledger=6,market_current=5,provenance_chains=5,readers='UNCHANGED',current_replay='UNCHANGED',
            collector='LOCKED',provider_requests=0,migrations_unchanged=True)))
    def test_ledger_version_key_hash_and_unknown_table_rejected(self):
        self.ready6()
        for bad,undo,code in [
            ("UPDATE m2_schema_migrations SET checksum=UNHEX(REPEAT('00',32)) WHERE version=6",
             "UPDATE m2_schema_migrations SET checksum=UNHEX('55457063c72d20498a097d273b5465d34cfd8aba5b2c7c229a9673bfc0c4a60c') WHERE version=6",'ledger_checksum'),
            ("UPDATE m2_schema_migrations SET migration_key='wrong' WHERE version=6",
             "UPDATE m2_schema_migrations SET migration_key='0006_fundamentals_and_payload_provenance' WHERE version=6",'schema6_ledger_keys'),
            ('CREATE TABLE m2_unknown (id INT PRIMARY KEY) ENGINE=InnoDB','DROP TABLE m2_unknown','table_set')]:
            self.sql(bad)
            try:self.assertEqual(self.probe()['code'],code)
            finally:self.sql(undo)
        self.sql('DELETE FROM m2_schema_migrations WHERE version=6')
        self.assertEqual(self.probe()['code'],'ledger_versions')
    def test_locked_anchors_and_active_cycles_fail_closed(self):
        self.ready6()
        for bad,undo in [
            ('UPDATE m2_jobs SET enabled=1','UPDATE m2_jobs SET enabled=0'),
            ("UPDATE m2_module_state SET status='ENABLED'","UPDATE m2_module_state SET status='LOCKED'"),
            ('UPDATE m2_collector_state SET stop_latched=0','UPDATE m2_collector_state SET stop_latched=1'),
            ('UPDATE m2_collector_state SET unresolved=1','UPDATE m2_collector_state SET unresolved=0'),
            ('UPDATE m2_collector_state SET pending_asset=1100','UPDATE m2_collector_state SET pending_asset=NULL'),
            ("INSERT INTO m2_collector_cycles (cycle_id,provider,owner_token,policy_hash,selection_json,status,started_utc) VALUES ('synthetic-cycle','boerse_frankfurt_api_v1','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',REPEAT('b',64),JSON_ARRAY(JSON_OBJECT('isin','SYNTHETIC','asset_id',1100),JSON_OBJECT('isin','SYNTHETIC','asset_id',1101),JSON_OBJECT('isin','SYNTHETIC','asset_id',1102),JSON_OBJECT('isin','SYNTHETIC','asset_id',1103),JSON_OBJECT('isin','SYNTHETIC','asset_id',1104)),'RUNNING','2026-01-01 01:00:00.000000')","DELETE FROM m2_collector_cycles"),
            ("INSERT INTO m2_collector_days VALUES ('boerse_frankfurt_api_v1','2026-01-01',0)","DELETE FROM m2_collector_days")]:
            self.sql(bad)
            try:self.assertFalse(self.probe()['ok'])
            finally:self.sql(undo)
        self.assertEqual(self.probe()['result'],dict(tables=26,ledger=6))
    def test_exact_new_metadata_and_market_provenance_fail_closed(self):
        self.ready6()
        for bad,undo in [
            ('ALTER TABLE m2_fundamental_metrics ADD COLUMN unexpected INT NULL','ALTER TABLE m2_fundamental_metrics DROP COLUMN unexpected'),
            ('ALTER TABLE m2_provider_fetches DROP INDEX ix_fetch_payload','ALTER TABLE m2_provider_fetches ADD KEY ix_fetch_payload (payload_sha256,payload_bytes,id)')]:
            self.sql(bad)
            try:self.assertFalse(self.probe()['ok'])
            finally:self.sql(undo)
        self.sql("UPDATE m2_market_current SET observation_dedupe_key=UNHEX(REPEAT('00',32)) WHERE asset_id=1100")
        before=self.baseline_rows();self.assertFalse(self.probe('current',allow_disabled=True)['ok'])
        self.assertEqual(self.baseline_rows(),before)
if __name__=='__main__':unittest.main()
