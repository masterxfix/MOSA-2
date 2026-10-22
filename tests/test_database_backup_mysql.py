"""Real MySQL8 dump/restore, only the verified ephemeral GitHub service."""
import copy,json,os,re,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts import database_backup as b
from scripts import collector_migration5 as migration
import test_migration5_mysql as fixtures
from test_collector_persistence_mysql import ENABLED,connect

ROOT=Path(__file__).resolve().parents[1]
ISOLATED=ENABLED and os.environ.get('MOSA2_BACKUP_RESTORE_ISOLATED')=='1'

def evidence(database,version):
    p=subprocess.run(['php',str(ROOT/'tests/backup_restore_mysql.php')],input=json.dumps(dict(database=database,version=version)),
        capture_output=True,text=True,timeout=30)
    b.require(p.returncode==0,'SHARED_VALIDATION_PROCESS_EXIT_'+str(p.returncode))
    b.require(not p.stderr,'SHARED_VALIDATION_PROCESS_DIAGNOSTIC')
    data=json.loads(p.stdout);b.require(data['ok'],data.get('code','SHARED_VALIDATION_REJECTED'));return data['result']

@unittest.skipUnless(ISOLATED,'temporary GitHub backup/restore MySQL8 service only')
class BackupMySQLTests(unittest.TestCase):
    sql=fixtures.Migration5MySQLTests.sql
    insert=fixtures.Migration5MySQLTests.insert
    seed=fixtures.Migration5MySQLTests.seed
    reset=fixtures.Migration5MySQLTests.reset
    def setUp(self):
        self.commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
        self.engine=b.IsolatedBackup(connect,evidence,self.commit)
        # Proof before EVERY destructive setup, including the reused source fixture.
        with connect() as c:self.engine.guard(c)
        self.reset();self.cleanup_targets();self.restore_account();self.seed_other_tables()
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.key=Ed25519PrivateKey.generate();self.password=os.urandom(32).hex()
    def tearDown(self):
        self.cleanup_targets()
        with connect() as c:
            self.engine.guard(c)
            with c.cursor() as q:q.execute("DROP USER IF EXISTS 'mosa2_restore_fixture'@'localhost'")
            c.commit()
        self.tmp.cleanup();self.key=None;self.password=None
    def cleanup_targets(self):
        with connect() as c:
            self.engine.guard(c)
            with c.cursor() as q:
                for db in sorted(b.TARGETS):q.execute('DROP DATABASE IF EXISTS '+b.qi(db))
            c.commit()
    def restore_account(self):
        # Passwordless socket-only SYNTHETIC fixture account, never a hosting credential.
        # Data/DDL grants exclude the source and all existing MOSA databases.
        with connect() as c:
            self.engine.guard(c)
            with c.cursor() as q:
                q.execute("DROP USER IF EXISTS 'mosa2_restore_fixture'@'localhost'")
                q.execute("CREATE USER 'mosa2_restore_fixture'@'localhost'")
                for target in sorted(b.TARGETS):
                    q.execute("GRANT ALL PRIVILEGES ON `"+target.replace('_','\\_')+"`.* TO 'mosa2_restore_fixture'@'localhost'")
                # Preserve original object DEFINERs. These grant no source-table DML.
                q.execute("GRANT SET_USER_ID,SYSTEM_USER ON *.* TO 'mosa2_restore_fixture'@'localhost'")
            c.commit()
    def seed_other_tables(self):
        at='2026-01-01 01:02:03.123456'
        self.insert('m2_relationships',dict(from_entity_id=1100,to_entity_id=1101,relationship_type='synthetic',source_id=201,valid_from=at,created_at=at))
        self.insert('m2_files',dict(entity_id=1100,source_id=201,storage_backend='synthetic',storage_key='NO_FILE_EXISTS',byte_size=32,sha256=bytes(range(32)),observed_at=at,created_at=at))
        self.insert('m2_files',dict(entity_id=1101,source_id=201,storage_backend='synthetic',storage_key='NO_HIGH_BYTE_FILE_EXISTS',byte_size=32,sha256=bytes(range(224,256)),observed_at=at,created_at=at))
        self.insert('m2_events',dict(event_type='synthetic',entity_id=1100,source_id=201,occurred_at=at,observed_at=at,metadata_json=json.dumps({'unicode':'\u00e4\U0001f9ea','zero':'\x00','exact':'123456789012345678.1234567890'}),created_at=at))
        self.insert('m2_jobs',dict(id=8800,job_key='synthetic_backup',module_key='backup_fixture',handler_key='UNWIRED',enabled=0,created_at=at,updated_at=at))
        self.insert('m2_job_runs',dict(job_id=8800,status='completed',started_at=at,finished_at=at,attempt_no=1,summary_json='{"synthetic":true}',created_at=at))
        self.insert('m2_sync_checkpoints',dict(source_id=201,stream_key='synthetic',cursor_value='exact\x00cursor',watermark_at=at,updated_at=at))
        self.insert('m2_module_state',dict(module_key='backup_fixture',schema_version=4,status='LOCKED',updated_at=at))
        self.insert('m2_market_bars',dict(asset_id=1100,source_id=201,route_id=7100,interval_key='1m',currency='EUR',starts_at='2026-01-01 00:00:00.123456',ends_at='2026-01-01 00:01:00.123456',
            open_price='123456789012345678.1234567890',high_price='123456789012345678.1234567891',low_price='123456789012345678.1234567889',close_price='123456789012345678.1234567890',observed_at=at,created_at=at))
        self.sql('ALTER TABLE m2_events AUTO_INCREMENT=12345')
        self.sql('CREATE TRIGGER backup_fixture_trigger BEFORE UPDATE ON m2_events FOR EACH ROW SET NEW.event_type=NEW.event_type')
        self.sql('CREATE PROCEDURE backup_fixture_procedure() SELECT COUNT(*) FROM m2_events')
        self.sql('CREATE FUNCTION backup_fixture_function(v INT) RETURNS INT DETERMINISTIC NO SQL RETURN v+1')
        self.sql("CREATE EVENT backup_fixture_event ON SCHEDULE AT '2099-01-01 00:00:00' DISABLE DO SET @backup_fixture_event=1")
    def backup(self,hook=None):return self.engine.backup(self.root,self.password,self.key,hook)
    def unpack(self):return b.unseal(self.root,self.password,self.key.public_key(),commit=self.commit,server_uuid=self.engine.uuid)
    def restore(self,target='mosa2_restore_isolated_a'):
        result=self.engine.restore(self.root,self.password,self.key.public_key(),target)
        if 'failure_code' in result:print(result['failure_code']) # fixed codes only, never SQL/client output
        return result
    def reseal(self,m,dump,state):
        for name in ('backup.sealed.json','manifest.json'):(self.root/name).unlink()
        m['dump_sha256']=b.sha(dump);raw=b.state_bytes(state);m['state_sha256']=b.sha(raw)
        m['table_sha256']={t:b.sha(b.canonical(rows)) for t,rows in state['rows'].items()}
        b.seal(self.root,m,dump,raw,self.password,self.key)
    def prove_schema_read_lock_consistency(self):
        import pymysql
        # Only the already verified ephemeral service, no hosting access.
        for sql in ('DROP TRIGGER backup_fixture_trigger','DROP PROCEDURE backup_fixture_procedure',
                    'DROP FUNCTION backup_fixture_function','DROP EVENT backup_fixture_event'):
            self.sql(sql)
        user='mosa2_schema_lock_fixture';locker=None
        with connect() as admin:
            self.engine.guard(admin)
            with admin.cursor() as q:
                q.execute("CREATE USER 'mosa2_schema_lock_fixture'@'localhost'")
                q.execute("GRANT ALL PRIVILEGES ON `h29077\\_mosa2\\_test`.* TO 'mosa2_schema_lock_fixture'@'localhost'")
            admin.commit()
        def session():
            c=pymysql.connect(host='127.0.0.1',port=3307,user=user,password='',database=b.SOURCE,
                autocommit=True,cursorclass=pymysql.cursors.DictCursor,connect_timeout=3,
                read_timeout=5,write_timeout=5,charset='utf8mb4')
            try:
                with c.cursor() as q:
                    q.execute('SELECT DATABASE() AS db,@@server_uuid AS uuid,@@hostname AS hostname,@@port AS port,CURRENT_USER() AS account')
                    self.assertEqual(q.fetchone(),dict(db=b.SOURCE,uuid=self.engine.uuid,hostname=self.engine.hostname,
                        port=3306,account=user+'@localhost'))
                    q.execute('SET SESSION lock_wait_timeout=1')
                    q.execute('SET SESSION innodb_lock_wait_timeout=1')
                return c
            except Exception:c.close();raise
        try:
            locker=session()
            with locker.cursor() as q:
                q.execute('SHOW GRANTS');grants=[next(iter(row.values())) for row in q.fetchall()]
                self.assertEqual(len(grants),2)
                self.assertEqual(sum(' ON *.* ' in g and g.startswith('GRANT USAGE ') for g in grants),1)
                q.execute('SET SESSION wait_timeout=20')
                names=migration.contract()['envelope4']['tables'];self.assertEqual(len(names),17)
                q.execute('LOCK TABLES '+','.join(b.qi(name)+' READ' for name in names))
            args=['--single-transaction','--quick','--skip-lock-tables','--no-tablespaces','--set-gtid-purged=OFF',
                  '--hex-blob','--tz-utc','--skip-routines','--events','--triggers','--default-character-set=utf8mb4',
                  '--column-statistics=0','--skip-comments','--skip-dump-date','--skip-add-locks',b.SOURCE]
            command=self.engine.sql_client('mysqldump',*args)
            command[command.index('--user=root')]='--user='+user
            dump=b.command(command,seconds=8)
            self.assertEqual(dump.count(b'CREATE TABLE `'),17)
            blocked={}
            for code,statement in (
                ('DML',"UPDATE m2_files SET storage_key=storage_key"),
                ('EXISTING_TABLE_DDL','ALTER TABLE m2_events ADD backup_lock_probe INT'),
                ('NEW_TABLE_DDL','CREATE TABLE m2_backup_lock_probe (id INT PRIMARY KEY) ENGINE=InnoDB')):
                with session() as competitor:
                    with competitor.cursor() as q:
                        try:q.execute(statement)
                        except pymysql.err.OperationalError as error:
                            self.assertEqual(error.args[0],1205);blocked[code]=True
                        else:blocked[code]=False
            print(json.dumps(dict(status='SCHEMA_READ_LOCK_PROOF',synthetic_export='PASS',blocked=blocked)))
            self.assertTrue(all(blocked.values()),'SCHEMA_READ_LOCK_DOES_NOT_BLOCK_ALL_DDL')
        finally:
            if locker is not None:
                try:
                    with locker.cursor() as q:q.execute('UNLOCK TABLES')
                finally:locker.close()
            with self.engine.database(b.SOURCE) as admin:
                with admin.cursor() as q:q.execute('DROP TABLE IF EXISTS m2_backup_lock_probe')
                admin.commit()
            with connect() as admin:
                self.engine.guard(admin)
                with admin.cursor() as q:q.execute("DROP USER 'mosa2_schema_lock_fixture'@'localhost'")
                admin.commit()

    def prove_schema_scoped_export(self):
        # Match the qualified hosting state: zero stored objects, no other
        # writers/DDL in this isolated one-test fixture. No global read lock.
        for sql in ('DROP TRIGGER backup_fixture_trigger','DROP PROCEDURE backup_fixture_procedure',
                    'DROP FUNCTION backup_fixture_function','DROP EVENT backup_fixture_event'):
            self.sql(sql)
        account='mosa2_schema_export_fixture'
        with connect() as c:
            self.engine.guard(c)
            with c.cursor() as q:
                q.execute("CREATE USER 'mosa2_schema_export_fixture'@'localhost'")
                q.execute("GRANT SELECT,SHOW VIEW,TRIGGER,EVENT,CREATE ROUTINE,ALTER ROUTINE,EXECUTE,LOCK TABLES ON `h29077\\_mosa2\\_test`.* TO 'mosa2_schema_export_fixture'@'localhost'")
            c.commit()
        try:
            with self.engine.database(b.SOURCE) as c:before=self.engine.snapshot(c,4)
            self.assertEqual(before['objects'],{})
            self.assertEqual(len(before['rows']),17)
            self.assertTrue(all(before['rows'].values()))
            for name in ('current','observations'):
                self.assertEqual(before['evidence'][name]['status'],'ok')
                self.assertEqual(len(before['evidence'][name]['items']),5)
            client=['docker','exec',self.engine.container,'mysql','--no-defaults','--protocol=socket','--user='+account,
                    '--batch','--skip-column-names','-e','SHOW GRANTS']
            grants=b.command(client).decode().splitlines()
            self.assertEqual(len(grants),2)
            self.assertEqual(sum(' ON *.* ' in g and g.startswith('GRANT USAGE ') for g in grants),1)
            self.assertEqual(sum(' ON `h29077' in g and ' TO ' in g for g in grants),1)
            # --routines is unnecessary only because complete visibility proves
            # zero routines. Never silently omit existing routine definitions.
            args=['--single-transaction','--quick','--skip-lock-tables','--no-tablespaces','--set-gtid-purged=OFF',
                  '--hex-blob','--tz-utc','--skip-routines','--events','--triggers','--default-character-set=utf8mb4',
                  '--column-statistics=0','--skip-comments','--skip-dump-date','--skip-add-locks',
                  '--skip-add-drop-table','--complete-insert','--order-by-primary',b.SOURCE]
            command=self.engine.sql_client('mysqldump',*args)
            command[command.index('--user=root')]='--user='+account
            dump=b.command(command)
            with self.engine.database(b.SOURCE) as c:self.assertEqual(self.engine.snapshot(c,4),before)
            identity='backup-'+__import__('uuid').uuid4().hex
            dump+=('-- MOSA2_BACKUP_COMPLETE:'+identity+'\n').encode();state=b.state_bytes(before)
            manifest=dict(format=b.FORMAT,backup_id=identity,database=b.SOURCE,schema_version=4,
                mysql_version=before['evidence']['properties']['version'],server_uuid=self.engine.uuid,commit=self.commit,
                dump_sha256=b.sha(dump),state_sha256=b.sha(state),migrations=before['evidence']['ledger'],
                table_sha256={t:b.sha(b.canonical(rows)) for t,rows in before['rows'].items()},
                consistency='CONTROLLED_SYNTHETIC_QUIESCENCE_NO_DDL_OR_WRITERS')
            b.seal(self.root,manifest,dump,state,self.password,self.key)
            self.assertEqual(self.unpack()[2],before)
            self.assertEqual(self.restore()['status'],'RESTORE_READBACK_PASS')
            with self.engine.database(b.SOURCE) as c:self.assertEqual(self.engine.snapshot(c,4),before)
            print('SCHEMA_ONLY_EXPORT_FULL_RESTORE_PASS_NO_GLOBAL_EXPORT_PRIVILEGES')
        finally:
            with connect() as c:
                self.engine.guard(c)
                with c.cursor() as q:q.execute("DROP USER 'mosa2_schema_export_fixture'@'localhost'")
                c.commit()

    def diagnose_restore_evidence(self):
        self.backup();expected=self.unpack()[2]['evidence']
        self.restore()
        with self.engine.database('mosa2_restore_isolated_a') as c:
            actual=self.engine.snapshot(c,4)['evidence']
        def first(a,b,path='$'):
            if type(a) is not type(b):return path
            if isinstance(a,dict):
                if a.keys()!=b.keys():return path
                for k in a:
                    diff=first(a[k],b[k],path+'.'+k)
                    if diff:return diff
            elif isinstance(a,list):
                if len(a)!=len(b):return path+'.length'
                for i,(x,y) in enumerate(zip(a,b)):
                    diff=first(x,y,path+'['+str(i)+']')
                    if diff:return diff
            elif a!=b:return path
            return None
        self.assertIsNone(first(expected,actual))

    def test_basis_restore(self):
        self.assertEqual(self.backup()['status'],'BACKUP_VERIFIED')
        before=self.unpack()[2]
        self.assertEqual(self.restore()['status'],'RESTORE_READBACK_PASS')
        with self.engine.database(b.SOURCE) as c:
            self.assertEqual(self.engine.snapshot(c,4),before)

    def test_complete_backup_restore_migrate5_then_fresh_schema4_restore(self):
        self.assertEqual(self.backup()['status'],'BACKUP_VERIFIED')
        m,dump,before=self.unpack();self.assertEqual(len(before['rows']),17)
        self.assertTrue(all(before['rows'].values()))
        self.assertEqual(len(before['objects']),4)
        self.assertEqual(len(before['evidence']['current']['items']),5)
        self.assertEqual(len(before['evidence']['observations']['items']),5)
        self.assertEqual(before['evidence']['current']['status'],'ok')
        self.assertTrue(all(item['status']=='stale' for item in before['evidence']['current']['items']))
        self.assertEqual(self.restore()['status'],'RESTORE_READBACK_PASS')
        with self.engine.database('mosa2_restore_isolated_a') as c:
            # Unchanged DDL, then bootstrap+ledger atomically; synthetic restore ONLY.
            with c.cursor() as q:
                for statement in migration.contract()['statements'][:5]:q.execute(statement)
            c.begin()
            with c.cursor() as q:
                for statement in migration.contract()['statements'][5:]:q.execute(statement)
                q.execute("INSERT INTO m2_schema_migrations VALUES (5,'0005_collector_reservations',%s,UTC_TIMESTAMP(6))",(bytes.fromhex(migration.EXPECTED_SHA),))
            c.commit()
        with self.engine.database('mosa2_restore_isolated_a') as read:after=self.engine.snapshot(read,5)
        self.assertEqual(len(after['rows']),21)
        for t,rows in before['rows'].items():
            actual=after['rows'][t]
            if t=='m2_jobs':actual=[r for r in actual if r['job_key']!='collector_reservations_v1']
            if t=='m2_module_state':actual=[r for r in actual if r['module_key']!='collector_reservations']
            if t=='m2_schema_migrations':actual=[r for r in actual if r['version']!=5]
            self.assertEqual(actual,rows,t)
        self.assertEqual(after['objects'],before['objects'])
        self.assertEqual(after['evidence']['current'],before['evidence']['current'])
        self.assertEqual(after['evidence']['observations'],before['evidence']['observations'])
        self.assertEqual(self.restore('mosa2_restore_isolated_b')['status'],'RESTORE_READBACK_PASS')
        self.assertEqual(self.unpack()[2],before)
        with self.engine.database(b.SOURCE) as c:self.assertEqual(self.engine.snapshot(c,4),before)
    def test_authentication_tamper_incomplete_and_wrong_identity(self):
        self.backup();original={n:(self.root/n).read_bytes() for n in ('backup.sealed.json','manifest.json')}
        for filename in original:
            raw=original[filename];(self.root/filename).write_bytes(raw[:-5]+b'XXXXX')
            with self.assertRaises(b.Rejected):self.restore()
            (self.root/filename).write_bytes(raw)
        signed=json.loads(original['manifest.json']);signed['manifest']['dump_sha256']='0'*64
        (self.root/'manifest.json').write_bytes(b.canonical(signed))
        with self.assertRaises(b.Rejected):self.restore()
        (self.root/'manifest.json').write_bytes(original['manifest.json'])
        with self.assertRaises(b.Rejected):b.unseal(self.root,self.password,Ed25519PrivateKey.generate().public_key(),commit=self.commit,server_uuid=self.engine.uuid)
        with self.assertRaises(b.Rejected):b.unseal(self.root,'SYNTHETIC_WRONG_KEY',self.key.public_key(),commit=self.commit,server_uuid=self.engine.uuid)
        for key,value in [('schema_version',5),('database','mosa_production'),('commit','0'*40),('server_uuid','0'*36)]:
            m,dump,state=self.unpack();m[key]=value;self.reseal(m,dump,state)
            with self.assertRaises(b.Rejected):self.restore()
            for n,raw in original.items():(self.root/n).write_bytes(raw)
        m,dump,state=self.unpack();self.reseal(m,dump[:-80],state)
        with self.assertRaisesRegex(b.Rejected,'DUMP_INCOMPLETE'):self.restore()
    def test_target_and_actual_server_guards_before_any_restore(self):
        self.backup()
        for target in [b.SOURCE,'mosa2_collector_isolated','mosa','mysql','../escape','mosa2_restore_isolated_a;DROP DATABASE mysql']:
            with self.assertRaisesRegex(b.Rejected,'RESTORE_TARGET_REJECTED'):self.restore(target)
        with patch.object(self.engine,'uuid','0'*36),connect() as c,self.assertRaisesRegex(b.Rejected,'ISOLATED_SERVER_IDENTITY_REQUIRED'):self.engine.guard(c)
        self.assertEqual(self.restore()['status'],'RESTORE_READBACK_PASS')
        with self.assertRaisesRegex(b.Rejected,'RESTORE_TARGET_EXISTS'):self.restore()
    def test_incomplete_dump_with_valid_signature_fails_full_readback(self):
        self.backup();m,dump,state=self.unpack()
        dump=re.sub(rb'^INSERT INTO `m2_files`[^\n]*\n',b'',dump,flags=re.M)
        self.reseal(m,dump,state)
        self.assertEqual(self.restore()['status'],'RESTORE_VERIFICATION_FAILED')
    def test_all_row_and_metadata_drift_is_detected_independently(self):
        self.backup();m,dump,before=self.unpack()
        for statement in ['DELETE FROM m2_files','UPDATE m2_market_current SET observation_dedupe_key=UNHEX(REPEAT(\'00\',32)) WHERE asset_id=1100',
            'ALTER TABLE m2_events AUTO_INCREMENT=54321','ALTER TABLE m2_relationships DROP FOREIGN KEY fk_relationships_source',
            "UPDATE m2_schema_migrations SET checksum=UNHEX(REPEAT('00',32)) WHERE version=4",'DROP TABLE m2_sync_checkpoints']:
            # A failed/unknown base restore aborts this method; never continue
            # subtests into the same existing target or retry that attempt.
            self.assertEqual(self.restore()['status'],'RESTORE_READBACK_PASS')
            with self.subTest(statement=statement):
                with self.engine.database('mosa2_restore_isolated_a') as c:
                    with c.cursor() as q:q.execute(statement)
                    c.commit()
                try:
                    with self.engine.database('mosa2_restore_isolated_a') as c:actual=self.engine.snapshot(c,4)
                except (b.Rejected,ValueError):pass
                else:self.assertNotEqual(actual,before)
                # Explicit fixture teardown after a KNOWN verified restore, not retry of uncertainty.
                self.cleanup_targets();(self.root/'restore-mosa2_restore_isolated_a.claim').unlink()
    def test_global_lock_blocks_real_concurrent_dml_and_ddl(self):
        observed=[]
        def competing():
            import pymysql
            for sql in ["UPDATE m2_files SET storage_key='MUST_NOT_COMMIT'",'ALTER TABLE m2_events ADD unexpected INT']:
                with self.engine.database(b.SOURCE) as c:
                    with c.cursor() as q:
                        q.execute('SET SESSION lock_wait_timeout=1')
                        with self.assertRaises(pymysql.err.OperationalError) as e:q.execute(sql)
                        self.assertEqual(e.exception.args[0],1205);observed.append(True)
                    c.rollback()
        self.backup(competing);self.assertEqual(observed,[True,True]);self.assertEqual(self.restore()['status'],'RESTORE_READBACK_PASS')
    def test_missing_object_visibility_export_abort_timeout_and_lost_connection(self):
        for failure in ('FULL_OBJECT_VISIBILITY_REQUIRED','PROCESS_TIMEOUT','PROCESS_CONNECTION_LOST'):
            method='visibility' if failure.startswith('FULL') else None
            ctx=patch.object(self.engine,method,side_effect=b.Rejected(failure)) if method else patch.object(b,'command',side_effect=b.Rejected(failure))
            with ctx,self.assertRaises(b.Rejected):self.backup()
            self.assertFalse((self.root/'manifest.json').exists())
        def interrupted():raise ConnectionError('SYNTHETIC PRIVATE ERROR')
        with self.assertRaisesRegex(b.Rejected,'BACKUP_ABORTED'):self.backup(interrupted)
        self.assertFalse((self.root/'backup.sealed.json').exists())
        original=self.engine.snapshot;control={}
        def remember(c,version):control['id']=c.thread_id();return original(c,version)
        def disconnect():
            with connect() as c:
                self.engine.guard(c)
                with c.cursor() as q:q.execute('KILL CONNECTION '+str(control['id']))
        with patch.object(self.engine,'snapshot',side_effect=remember),self.assertRaisesRegex(b.Rejected,'BACKUP_ABORTED'):
            self.backup(disconnect)
        self.assertFalse((self.root/'manifest.json').exists())
    def test_restore_failure_unknown_result_and_no_automatic_retry(self):
        self.backup()
        with patch.object(b,'command',side_effect=b.Rejected('PROCESS_CONNECTION_LOST')):
            result=self.restore('mosa2_restore_isolated_fault')
        self.assertEqual(result,dict(status='RESTORE_OUTCOME_UNKNOWN',retry_allowed=False))
        with self.assertRaises(b.Rejected):self.restore('mosa2_restore_isolated_fault')
    def test_partial_real_restore_never_claims_rollback_or_success(self):
        self.backup();m,dump,state=self.unpack()
        # Real successful DDL/DML followed by a client SQL error; target remains partial.
        end=('-- MOSA2_BACKUP_COMPLETE:'+m['backup_id']+'\n').encode()
        self.reseal(m,dump[:-len(end)]+b'INVALID SYNTHETIC SQL;\n'+end,state)
        result=self.restore();self.assertEqual(result,dict(status='RESTORE_PARTIAL_FAILED',retry_allowed=False,failure_code='RESTORE_SQL_SYNTAX_REJECTED'))
        with self.assertRaises(b.Rejected):self.restore()
    def test_restore_session_cannot_mutate_original_database(self):
        self.backup();m,dump,state=self.unpack();before=self.sql('SELECT * FROM m2_files')
        end=('-- MOSA2_BACKUP_COMPLETE:'+m['backup_id']+'\n').encode()
        self.reseal(m,dump[:-len(end)]+b'DELETE FROM h29077_mosa2_test.m2_files;\n'+end,state)
        self.assertEqual(self.restore()['status'],'RESTORE_PARTIAL_FAILED')
        self.assertEqual(self.sql('SELECT * FROM m2_files'),before)

if __name__=='__main__':unittest.main()
