"""Synthetic destructive tests ONLY through the existing guarded GitHub MySQL service."""
import copy,hashlib,json,subprocess,unittest
from pathlib import Path
from scripts import collector_migration5 as m
from test_collector_persistence_mysql import ENABLED,connect

@unittest.skipUnless(ENABLED,'temporary GitHub MySQL8 service only')
class Migration5MySQLTests(unittest.TestCase):
    def sql(self,sql,args=(),*,admin=False):
        with connect() as c:
            with c.cursor() as q:
                if not admin:q.execute('USE h29077_mosa2_test')
                q.execute(sql,args);rows=q.fetchall() if q.description else []
            c.commit();return rows
    def setUp(self):self.reset()
    def reset(self):
        # connect() first proves GHA opt-in, loopback, MySQL8, and the service-only database.
        self.sql('DROP DATABASE IF EXISTS h29077_mosa2_test',admin=True)
        self.sql('CREATE DATABASE h29077_mosa2_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci',admin=True)
        for n in range(1,5):
            path=next((m.ROOT/'docs/database/migrations').glob(f'{n:04d}_*.sql'))
            text='\n'.join(x for x in path.read_text().splitlines() if not x.lstrip().startswith('--'))
            for statement in text.split(';'):
                if statement.strip():self.sql(statement)
            self.sql('INSERT INTO m2_schema_migrations VALUES (%s,%s,%s,UTC_TIMESTAMP(6))',
                     (n,f'{n:04d}_'+['core_asset_identity','market_current_history','market_units','current_observation_provenance'][n-1],bytes.fromhex(hashlib.sha256(path.read_bytes()).hexdigest())))
        self.seed()
    def insert(self,table,row):
        names=list(row);self.sql('INSERT INTO '+table+' ('+','.join(names)+') VALUES ('+','.join(['%s']*len(names))+')',tuple(row.values()))
    def seed(self):
        now='2026-01-01 00:00:00.000000'
        seed=json.loads((m.ROOT/'api/market_core/units.json').read_text())['definitions']
        for d in seed:
            d={k:v for k,v in d.items() if k!='definition_reference'};d['definition_sha256']=bytes.fromhex(d['definition_sha256']);d['created_at']=now;self.insert('m2_units',d)
        p=subprocess.run(['php',str(m.ROOT/'tests/fixtures/migration5_seed.php'),str(m.ROOT)],capture_output=True,text=True,check=True)
        rows=json.loads(p.stdout)
        self.insert('m2_sources',dict(id=201,source_key='provider:boerse_frankfurt_api',source_type='market_data',display_name='Synthetic source',enabled=1,created_at=now,updated_at=now))
        for entry in rows:
            r=entry['route'];asset=r['asset_id']
            self.insert('m2_entities',dict(id=asset,entity_type='asset',canonical_name='SYNTHETIC',status='active',created_at=now,updated_at=now))
            self.insert('m2_assets',dict(entity_id=asset,asset_class='equity',display_name='SYNTHETIC',status='active',created_at=now,updated_at=now))
            self.insert('m2_asset_identifiers',dict(asset_id=asset,identifier_type='isin',identifier_value=entry['isin'],normalized_value=entry['isin'],is_primary=1,created_at=now))
            route={k:r[k] for k in ('asset_id','source_id','route_revision','route_type','external_key','priority','enabled','unit_contract_version','quote_unit_key','quote_unit_version','quantity_basis_unit_key','quantity_basis_unit_version','quantity_basis_amount','volume_unit_key','volume_unit_version')}
            route.update(id=r['route_id'],created_at=now,updated_at=now);self.insert('m2_asset_source_routes',route)
            f=entry['fact'];f['dedupe_key']=bytes.fromhex(f['dedupe_key']);f['created_at']=now;self.insert('m2_market_observations',f)
            current=entry['current'];current['observation_dedupe_key']=bytes.fromhex(current['observation_dedupe_key']);self.insert('m2_market_current',current)
    def fixture(self,operation='capture',**kwargs):
        p=subprocess.run(['php',str(m.ROOT/'tests/migration5_mysql.php')],input=json.dumps(dict(operation=operation,**kwargs)),capture_output=True,text=True,check=True)
        self.assertEqual(p.stderr,'');reply=json.loads(p.stdout)
        self.assertTrue(reply['ok'],reply);return reply['result']
    def ledger5(self):self.sql("INSERT INTO m2_schema_migrations VALUES (5,'0005_collector_reservations',%s,UTC_TIMESTAMP(6))",(bytes.fromhex(m.EXPECTED_SHA),))
    def migrate(self):
        for sql in m.contract()['statements']:self.sql(sql)
        self.ledger5()
    def baseline_rows(self):
        out={}
        for table in m.contract()['envelope4']['tables']:
            if table in {'m2_jobs','m2_module_state','m2_schema_migrations'}:continue
            out[table]=self.sql('SELECT * FROM '+table)
        return out
    def test_complete_migration_exact_structure_current_observations_readback_and_replay_block(self):
        before=self.fixture();self.assertIsInstance(before['collector'],dict)
        m.php(dict(operation='audit',inventory=before['inventory'],version=4))
        self.assertEqual(m.assess(before)['status'],'SCHEMA4_READY')
        old=self.baseline_rows();web=self.fixture('current');contracts4=self.fixture('contracts',version=4)
        plan=m.prepare(before,'a'*40,'synthetic-migration',dict(classification='A'))
        self.assertFalse(plan['execution_authorized']);self.assertEqual(len(plan['steps']),8)
        self.migrate();after=self.fixture();self.assertEqual(m.assess(after)['status'],'SCHEMA5_LOCKED_COMPLETE')
        wire=self.fixture('wire');self.assertLess(len(json.dumps(wire).encode()),65536)
        self.assertEqual(m.unpack(wire['migration5']),after)
        self.assertEqual(self.baseline_rows(),old);self.assertEqual(self.fixture('current'),web)
        self.assertEqual(len(web['current']['items']),5);self.assertEqual(len(web['observations']['items']),5)
        contracts5=self.fixture('contracts',version=5)
        for table in old:self.assertEqual(contracts4['snapshot'][table],contracts5['snapshot'][table])
        self.assertFalse(m.assess(after)['apply_allowed'])
        with self.assertRaises(ValueError):m.prepare(after,'a'*40,'replay',{})
        with self.assertRaises(Exception):self.sql(m.contract()['statements'][0])
        self.assertEqual(self.fixture(),after)
    def test_each_ddl_and_bootstrap_interruption_blocks_without_repair(self):
        for cut in range(1,9):
            with self.subTest(cut=cut):
                self.reset()
                for sql in m.contract()['statements'][:cut]:self.sql(sql)
                data=self.fixture();result=m.assess(data)
                self.assertEqual(result['status'],'PARTIAL_OR_CONFLICT');self.assertFalse(result['apply_allowed'])
                with self.assertRaises(ValueError):m.prepare(data,'a'*40,'interrupted',{})
                self.assertEqual(self.fixture(),data)
    def test_name_structure_ledger_and_anchor_conflicts(self):
        self.sql('CREATE TABLE m2_collector_requests (wrong INT PRIMARY KEY) ENGINE=InnoDB')
        self.assertEqual(m.assess(self.fixture())['status'],'PARTIAL_OR_CONFLICT')
        self.reset();self.migrate();good=self.fixture()
        for kind in ('missing_ledger','checksum','key','module','job','state','unknown_column','unknown_table'):
            bad=copy.deepcopy(good)
            if kind=='missing_ledger':bad['ledger'].pop()
            elif kind=='checksum':bad['ledger'][-1]['checksum']='0'*64
            elif kind=='key':bad['ledger'][-1]['migration_key']='wrong'
            elif kind=='module':bad['modules'][0]['status']='ENABLED'
            elif kind=='job':bad['jobs'][0]['enabled']='1'
            elif kind=='state':bad['collector']['m2_collector_state'][0]['stop_latched']='0'
            elif kind=='unknown_table':bad['inventory'][0]['rows'].append({'TABLE_NAME':'unexpected'})
            else:
                columns=next(x for x in bad['inventory'] if 'information_schema.columns' in x['sql'] and x['args']==['m2_collector_state']);columns['rows'][0]['COLUMN_TYPE']='varchar(63)'
            self.assertNotIn(m.assess(bad)['status'],('SCHEMA4_READY','SCHEMA5_LOCKED_COMPLETE'),kind)
    def reject(self,sql,args=()):
        import pymysql
        with self.assertRaises(pymysql.MySQLError):self.sql(sql,args)
    def test_all_foreign_unique_and_check_contracts_are_enforced(self):
        self.migrate();provider='boerse_frankfurt_api_v1';day='2026-01-01';at='2026-01-01 01:00:00.000000'
        selection=json.dumps([dict(isin='SYNTHETIC',asset_id=1100)]*5)
        self.sql("INSERT INTO m2_collector_cycles (cycle_id,provider,owner_token,policy_hash,selection_json,status,started_utc) VALUES ('cycle1',%s,%s,%s,%s,'RUNNING',%s)",(provider,'a'*36,'b'*64,selection,at))
        self.sql('INSERT INTO m2_collector_days VALUES (%s,%s,0)',(provider,day))
        self.sql("INSERT INTO m2_collector_requests (cycle_id,asset_id,ordinal_no,provider,reserved_utc,berlin_day) VALUES ('cycle1',1100,1,%s,%s,%s)",(provider,at,day))
        for assignment in ('job_id=999999','pending_asset=999999',"active_cycle='missing'","last_confirmed_cycle='missing'",'stop_latched=2',"status='INVALID'"):
            self.reject('UPDATE m2_collector_state SET '+assignment)
        self.reject('INSERT INTO m2_collector_state SELECT * FROM m2_collector_state')
        self.reject("INSERT INTO m2_collector_state(provider,job_id) SELECT 'other',job_id FROM m2_collector_state")
        for assignment in ("provider='missing'",'reserved_count=6','confirmed_attempts=1',"selection_json='[]'","status='INVALID'","finished_utc='2025-01-01'"):
            self.reject('UPDATE m2_collector_cycles SET '+assignment)
        self.reject('INSERT INTO m2_collector_cycles SELECT * FROM m2_collector_cycles')
        self.reject("INSERT INTO m2_collector_cycles SELECT 'cycle2',provider,owner_token,policy_hash,selection_json,status,started_utc,finished_utc,reserved_count,confirmed_attempts,error_code FROM m2_collector_cycles")
        self.reject("UPDATE m2_collector_days SET provider='missing'");self.reject('INSERT INTO m2_collector_days SELECT * FROM m2_collector_days')
        for assignment in ("cycle_id='missing'",'asset_id=999999',"berlin_day='2026-01-02'",'ordinal_no=0','attempt_confirmed=2',"status='INVALID'","finished_utc='2025-01-01'"):
            self.reject('UPDATE m2_collector_requests SET '+assignment)
        self.reject('INSERT INTO m2_collector_requests SELECT * FROM m2_collector_requests')
        self.reject("INSERT INTO m2_collector_requests SELECT cycle_id,1101,ordinal_no,provider,reserved_utc,berlin_day,status,attempt_confirmed,finished_utc FROM m2_collector_requests")
if __name__=='__main__':unittest.main()
