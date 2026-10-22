"""Bounded logical backup protocol. DB execution is HARD LIMITED to the synthetic CI service.

No CLI, hosting configuration, credential loading, retry, production restore or migration.
The existing test connection factory is injected, not replaced.
"""
import base64
import contextlib
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

from scripts import collector_migration5 as migration
# Reuse the existing script's import convention without changing its pinned bytes.
sys.path.insert(0,str(Path(__file__).resolve().parent))
try:
    import deploy_test_sftp as encryption
finally:
    sys.path.pop(0)
from scripts.collector_release import canonical, decode

SOURCE='h29077_mosa2_test'
TARGETS=frozenset({'mosa2_restore_isolated_a','mosa2_restore_isolated_b','mosa2_restore_isolated_fault'})
FORMAT='mosa2-isolated-backup-v1'
DUMP_LIMIT=8*1024*1024
STATE_LIMIT=16*1024*1024
FILE_LIMIT=36*1024*1024
ROW_LIMIT=100000
CELL_LIMIT=1024*1024
SECONDS=90

class Rejected(RuntimeError): pass

def require(ok,code):
    if not ok:raise Rejected(code)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def qi(name):
    require(isinstance(name,str) and re.fullmatch('[a-z][a-z_0-9]*',name),'IDENTIFIER_REJECTED')
    return '`'+name+'`'

def database_name(c):
    # PyMySQL select_db() changes the server DB but does not update Connection.db.
    with c.cursor() as q:
        q.execute('SELECT DATABASE() AS db');name=q.fetchone()['db']
    require(name in {SOURCE,*TARGETS},'DATABASE_SCOPE_REJECTED');return name

def value(v):
    if v is None or type(v) in (str,int):return v
    if isinstance(v,bytes):return {'binary':base64.b64encode(v).decode('ascii')}
    if isinstance(v,Decimal):return {'decimal':format(v,'f')}
    if isinstance(v,datetime):return {'datetime6':v.isoformat(sep=' ',timespec='microseconds')}
    if isinstance(v,date):return {'date':v.isoformat()}
    raise Rejected('VALUE_TYPE_REJECTED')

def private(path,directory=False):
    path=Path(path).absolute()
    require(not any(p.is_symlink() for p in (path,*path.parents)),'BACKUP_SYMLINK_REJECTED')
    require(path.is_dir() if directory else path.is_file(),'BACKUP_FILE_MISSING')
    if os.name=='posix':
        s=path.stat();require(s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==(0o700 if directory else 0o600),'BACKUP_MODE_REJECTED')
    return path

def command(argv,*,input_bytes=b'',limit=DUMP_LIMIT,seconds=SECONDS):
    """Anonymous private files, bounded output/time; SQL/client diagnostics never escape."""
    with tempfile.TemporaryFile() as inp,tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        inp.write(input_bytes);inp.seek(0);p=None;deadline=time.monotonic()+seconds
        try:
            def file_limit():
                import resource
                maximum=max(limit,65536);resource.setrlimit(resource.RLIMIT_FSIZE,(maximum,maximum))
            p=subprocess.Popen(argv,stdin=inp,stdout=out,stderr=err,preexec_fn=file_limit if os.name=='posix' else None,
                env={k:v for k,v in os.environ.items() if k not in ('MYSQL_PWD','MYSQL_TEST_LOGIN_FILE')})
            while p.poll() is None:
                require(time.monotonic()<deadline,'PROCESS_TIMEOUT')
                require(os.fstat(out.fileno()).st_size<=limit and os.fstat(err.fileno()).st_size<=65536,'PROCESS_SIZE_LIMIT')
                time.sleep(.01)
            if p.returncode!=0:
                err.seek(0);codes=re.findall(rb'ERROR ([0-9]+) \([A-Z0-9]{5}\)',err.read(65536))
                known=bool(codes) and not any(int(code) in (2006,2013,2055) for code in codes)
                if p.returncode>0 and known:raise Rejected('PROCESS_SQL_FAILED',int(codes[0]))
                raise Rejected('PROCESS_CONNECTION_LOST')
            require(os.fstat(out.fileno()).st_size<=limit and os.fstat(err.fileno()).st_size==0,'PROCESS_OUTPUT_REJECTED')
            out.seek(0);return out.read(limit+1)
        except Rejected:raise
        except Exception:raise Rejected('PROCESS_CONNECTION_LOST') from None
        finally:
            if p is not None and p.poll() is None:p.kill();p.wait(timeout=5)

def seal(root,manifest,dump,state,password,signing_key):
    """Reuse the established AES-GCM/HKDF envelope; bind it to a trusted Ed25519 key."""
    root=private(root,True)
    require(not any((root/name).exists() or (root/name).is_symlink() for name in
        ('backup.sealed.json','manifest.json','mosa2-web-backup.sealed.json','mosa2-web-before.json')),'BACKUP_OUTPUT_EXISTS')
    require(len(dump)<=DUMP_LIMIT and len(state)<=STATE_LIMIT,'BACKUP_SIZE_LIMIT')
    payload_bound=4*((len(dump)+2)//3)+4*((len(state)+2)//3)+len(json.dumps(manifest).encode())+1024
    require(4*((payload_bound+18)//3)+1024<=FILE_LIMIT,'BACKUP_SIZE_LIMIT')
    previous=os.environ.get('RUNNER_TEMP');os.environ['RUNNER_TEMP']=str(root)
    oldmask=os.umask(0o077)
    try:
        encryption.persist_backup(manifest,{'dump.sql':base64.b64encode(dump).decode(),'state.json':base64.b64encode(state).decode()},password)
        envelope=(root/'mosa2-web-backup.sealed.json').read_bytes()
        require(len(envelope)<=FILE_LIMIT,'BACKUP_SIZE_LIMIT')
        (root/'mosa2-web-before.json').unlink()
        sealed=root/'backup.sealed.json';(root/'mosa2-web-backup.sealed.json').rename(sealed)
        checked=dict(manifest=manifest,envelope_sha256=sha(envelope))
        checked['signature']=base64.b64encode(signing_key.sign(canonical(checked))).decode()
        with (root/'manifest.json').open('xb') as f:f.write(canonical(checked))
    finally:
        os.umask(oldmask)
        if previous is None:os.environ.pop('RUNNER_TEMP',None)
        else:os.environ['RUNNER_TEMP']=previous
    return sealed,root/'manifest.json'

def state_bytes(snapshot):
    # PDO numeric replay needs the original SHOW CREATE field order.
    # Manifest signatures and per-table content hashes still use canonical JSON.
    return json.dumps(snapshot,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()

def unseal(root,password,public_key,*,commit,server_uuid):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    stage='BACKUP_AUTHENTICATION_REJECTED'
    try:
        root=private(root,True);ep=private(root/'backup.sealed.json');mp=private(root/'manifest.json')
        require(ep.stat().st_size<=FILE_LIMIT and mp.stat().st_size<=65536,'BACKUP_SIZE_LIMIT')
        raw=mp.read_bytes();signed=decode(raw);require(raw==canonical(signed) and set(signed)=={'manifest','envelope_sha256','signature'},'MANIFEST_CANONICAL_REJECTED')
        signature=base64.b64decode(signed.pop('signature'),validate=True);public_key.verify(signature,canonical(signed))
        envelope=ep.read_bytes();require(sha(envelope)==signed['envelope_sha256'],'ENVELOPE_HASH_REJECTED')
        m=signed['manifest']
        require(set(m)=={'format','backup_id','database','schema_version','mysql_version','server_uuid','commit','dump_sha256','state_sha256','migrations','table_sha256','consistency'},'BACKUP_MANIFEST_REJECTED')
        require(m['format']==FORMAT and m['schema_version']==4 and m['database']==SOURCE and m['commit']==commit
            and m['server_uuid']==server_uuid,'BACKUP_IDENTITY_REJECTED')
        require(re.fullmatch('[0-9a-f]{40}',commit) and re.fullmatch('backup-[0-9a-f]{32}',m['backup_id']),'BACKUP_IDENTITY_REJECTED')
        e=decode(envelope);context=b'mosa2-testsite-web-backup-v1';require(e['context']==context.decode(),'ENCRYPTION_CONTEXT_REJECTED')
        key=HKDF(algorithm=hashes.SHA256(),length=32,salt=base64.b64decode(e['salt'],validate=True),info=context).derive(password.encode())
        payload=decode(AESGCM(key).decrypt(base64.b64decode(e['nonce'],validate=True),base64.b64decode(e['ciphertext'],validate=True),context))
        require(payload['before']==m and set(payload['files'])=={'dump.sql','state.json'},'BACKUP_MANIFEST_REJECTED')
        dump=base64.b64decode(payload['files']['dump.sql'],validate=True);state=base64.b64decode(payload['files']['state.json'],validate=True)
        require(len(dump)<=DUMP_LIMIT and len(state)<=STATE_LIMIT,'BACKUP_SIZE_LIMIT')
        require(sha(dump)==m['dump_sha256'] and sha(state)==m['state_sha256'],'BACKUP_CONTENT_HASH_REJECTED')
        require(dump.endswith(('-- MOSA2_BACKUP_COMPLETE:'+m['backup_id']+'\n').encode()),'DUMP_INCOMPLETE')
        stage='BACKUP_STATE_DECODE_REJECTED'
        snapshot=decode(state)
        require(m['mysql_version']==snapshot['evidence']['properties']['version'],'BACKUP_VERSION_REJECTED')
        require(snapshot['schema_version']==4 and sorted(snapshot['rows'])==migration.contract()['envelope4']['tables'],'BACKUP_TABLE_SET_REJECTED')
        require(m['migrations']==snapshot['evidence']['ledger'],'BACKUP_LEDGER_REJECTED')
        stage='BACKUP_LEDGER_VALIDATION_REJECTED'
        expected=migration.contract()['envelope4'];ledger=m['migrations']
        require([str(r['version']) for r in ledger]==expected['versions'] and [r['checksum'].lower() for r in ledger]==expected['digests'],'BACKUP_LEDGER_REJECTED')
        stage='BACKUP_SCHEMA_VALIDATION_REJECTED'
        migration.php(dict(operation='audit',inventory=snapshot['evidence']['inventory'],version=4))
        require(m['table_sha256']=={t:sha(canonical(rows)) for t,rows in snapshot['rows'].items()},'BACKUP_ROWS_REJECTED')
        return m,dump,snapshot
    except Rejected:raise
    except Exception:raise Rejected(stage) from None

class IsolatedBackup:
    """Execution has no arbitrary server/DB/user/credential arguments or production mode."""
    def __init__(self,connect,evidence,commit):
        require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('MOSA2_ISOLATED_MYSQL')=='1'
            and os.environ.get('MOSA2_BACKUP_RESTORE_ISOLATED')=='1','ISOLATED_BACKUP_MODE_REQUIRED')
        self.container=os.environ.get('MOSA2_MYSQL_CONTAINER','')
        self.uuid=os.environ.get('MOSA2_ISOLATED_SERVER_UUID','');self.hostname=os.environ.get('MOSA2_ISOLATED_SERVER_HOSTNAME','')
        require(re.fullmatch('[0-9a-f]{12,64}',self.container) and re.fullmatch('[0-9a-f-]{36}',self.uuid) and self.hostname,'ISOLATED_CONTAINER_REQUIRED')
        require(re.fullmatch('[0-9a-f]{40}',commit),'BACKUP_COMMIT_REQUIRED')
        self.connect=connect;self.evidence=evidence;self.commit=commit

    def guard(self,c,database='mosa2_collector_isolated'):
        require(c.host=='127.0.0.1' and c.port==3307 and c.user in ('root',b'root'),'ISOLATED_TRANSPORT_REQUIRED')
        with c.cursor() as q:
            q.execute('SELECT DATABASE() AS db,VERSION() AS version,@@port AS port,@@server_uuid AS uuid,@@hostname AS hostname,@@event_scheduler AS scheduler,@@partial_revokes AS partial_revokes')
            r=q.fetchone()
        require(r['db']==database and database in {SOURCE,'mosa2_collector_isolated',*TARGETS}
            and r['version'].startswith('8.0.') and r['port']==3306 and r['uuid']==self.uuid
            and r['hostname']==self.hostname and r['scheduler']=='OFF' and r['partial_revokes']==0,'ISOLATED_SERVER_IDENTITY_REQUIRED')
        c.rollback()
        return r

    @contextlib.contextmanager
    def database(self,name):
        require(name in {SOURCE,*TARGETS},'DATABASE_SCOPE_REJECTED')
        with self.connect() as c:
            self.guard(c);c.select_db(name);self.guard(c,name)
            with c.cursor() as q:
                q.execute("SET SESSION time_zone='+00:00'");q.execute('SET SESSION max_execution_time=10000');q.execute('SET SESSION lock_wait_timeout=2')
            yield c

    def sql_client(self,program,*args):
        require(program in ('mysql','mysqldump'),'BACKUP_CLIENT_REJECTED')
        return ['docker','exec',*(['-i'] if program=='mysql' else []),self.container,program,
            '--no-defaults','--protocol=socket','--user='+('mosa2_restore_fixture' if program=='mysql' else 'root'),*args]

    def visibility(self,c):
        with c.cursor() as q:
            q.execute('SELECT CURRENT_USER() AS user');principal=q.fetchone()['user']
            require(principal in ('root@%','root@localhost'),'FULL_OBJECT_PRINCIPAL_REQUIRED')
            user,host=principal.split('@')
            q.execute('SELECT PRIVILEGE_TYPE FROM information_schema.USER_PRIVILEGES WHERE GRANTEE=%s',("'"+user+"'@'"+host+"'",))
            grants={r['PRIVILEGE_TYPE'] for r in q.fetchall()}
        # MySQL8 SHOW GRANTS expands global ALL into individual privileges.
        # Global SELECT exposes routine definitions; TRIGGER/EVENT cover all object names.
        require({'SELECT','SHOW VIEW','TRIGGER','EVENT','RELOAD'}<=grants,'FULL_OBJECT_VISIBILITY_REQUIRED')

    def snapshot(self,c,version):
        from pymysql.cursors import SSDictCursor
        deadline=time.monotonic()+SECONDS
        self.visibility(c)
        c.rollback()
        with c.cursor() as q:
            q.execute('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            q.execute('SET SESSION TRANSACTION READ ONLY')
            q.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT')
            q.execute('SELECT @@session.transaction_read_only AS ro');require(q.fetchone()['ro']==1,'BACKUP_READ_ONLY_REQUIRED')
            q.execute("SELECT @@session.time_zone AS tz");require(q.fetchone()['tz']=='+00:00','BACKUP_UTC_REQUIRED')
            q.execute('SELECT TABLE_NAME,ENGINE,AUTO_INCREMENT,TABLE_COLLATION,ROW_FORMAT,CREATE_OPTIONS FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')
            metadata=q.fetchall()
            require([r['TABLE_NAME'] for r in metadata]==migration.contract()[f'envelope{version}']['tables'],'BACKUP_TABLE_SET_REJECTED')
            require(all(r['ENGINE']=='InnoDB' for r in metadata),'BACKUP_ENGINE_REJECTED')
        rows={};budget=0
        for table in metadata:
            name=table['TABLE_NAME']
            with c.cursor() as q:
                q.execute('SHOW COLUMNS FROM '+qi(name));columns=[r['Field'] for r in q.fetchall()]
                q.execute('SHOW KEYS FROM '+qi(name)+" WHERE Key_name='PRIMARY'");pk=sorted(q.fetchall(),key=lambda x:x['Seq_in_index'])
                require(pk,'BACKUP_PRIMARY_KEY_REQUIRED')
                q.execute('SELECT 1 FROM '+qi(name)+' WHERE '+' OR '.join('OCTET_LENGTH('+qi(col)+')>'+str(CELL_LIMIT) for col in columns)+' LIMIT 1')
                require(q.fetchone() is None,'BACKUP_CELL_LIMIT')
            data=[]
            with c.cursor(SSDictCursor) as q:
                q.execute('SELECT * FROM '+qi(name)+' ORDER BY '+','.join(qi(r['Column_name']) for r in pk)+' LIMIT '+str(ROW_LIMIT+1))
                try:
                    for row in q:
                        require(time.monotonic()<deadline,'BACKUP_TIMEOUT')
                        item={k:value(v) for k,v in row.items()};budget+=len(canonical(item))
                        require(len(data)<ROW_LIMIT and budget<STATE_LIMIT,'BACKUP_SIZE_LIMIT');data.append(item)
                except Exception:
                    # Do not drain an oversized server-side result in cursor.close().
                    c.close();raise
            rows[name]=data
        evidence=self.evidence(database_name(c),version)
        # Existing exact schema parser and runtime ledger/unit contracts; no new schema checker.
        inventory=json.loads(json.dumps(evidence['inventory']))
        for entry in inventory:
            # This existing CHECK query has no ORDER BY. MySQL may enumerate the
            # same constraints differently after SHOW CREATE/dump recreation.
            if entry['sql'].startswith('SELECT c.CONSTRAINT_NAME,c.CHECK_CLAUSE FROM information_schema.check_constraints c '):
                entry['rows'].sort(key=lambda row:row['CONSTRAINT_NAME'])
            for row in entry['rows']:
                if entry['sql']=='SELECT DATABASE() AS db,VERSION() AS version,@@port AS port,@@foreign_key_checks AS fk_checks':
                    require(row['db']==database_name(c),'DATABASE_SCOPE_REJECTED');row['db']=SOURCE
                if 'REFERENCED_TABLE_SCHEMA' in row:
                    require(row['REFERENCED_TABLE_SCHEMA']==database_name(c),'FOREIGN_SCHEMA_REJECTED');row['REFERENCED_TABLE_SCHEMA']=SOURCE
        migration.php(dict(operation='audit',inventory=inventory,version=version))
        evidence['inventory']=inventory;evidence['properties']['db']=SOURCE
        objects=self.objects(c)
        return dict(schema_version=version,rows=rows,metadata=[{k:value(v) for k,v in t.items()} for t in metadata],evidence=evidence,objects=objects)

    def objects(self,c):
        out={}
        for kind,namecol,table in [('TRIGGER','TRIGGER_NAME','triggers'),('PROCEDURE','ROUTINE_NAME','routines'),('FUNCTION','ROUTINE_NAME','routines'),('EVENT','EVENT_NAME','events')]:
            schema={'triggers':'TRIGGER_SCHEMA','routines':'ROUTINE_SCHEMA','events':'EVENT_SCHEMA'}[table]
            with c.cursor() as q:
                q.execute('SELECT '+namecol+' FROM information_schema.'+table+' WHERE '+schema+'=DATABASE()'+(" AND ROUTINE_TYPE=%s" if table=='routines' else '')+' ORDER BY '+namecol, (kind,) if table=='routines' else ())
                names=[r[namecol] for r in q.fetchall()];require(len(names)<=32,'BACKUP_OBJECT_LIMIT')
                for name in names:
                    q.execute('SHOW CREATE '+kind+' '+qi(name));row=q.fetchone()
                    for v in row.values():
                        if isinstance(v,str):require(not re.search(r'`?'+re.escape(database_name(c))+r'`?\s*\.',v),'OBJECT_QUALIFIED_REFERENCE_UNSUPPORTED')
                    # MySQL regenerates object creation time; it is not user DATETIME data.
                    out[kind+':'+name]={k:value(v) for k,v in row.items() if k!='Created'}
        return out

    def backup(self,root,password,signing_key,hook=None):
        root=private(root,True);start=time.monotonic()
        require(not any((root/name).exists() or (root/name).is_symlink() for name in
            ('backup.sealed.json','manifest.json','mosa2-web-backup.sealed.json','mosa2-web-before.json')),'BACKUP_OUTPUT_EXISTS')
        try:
            with self.database(SOURCE) as c:
                self.visibility(c)
                with c.cursor() as q:q.execute('FLUSH TABLES WITH READ LOCK')
                try:
                    before=self.snapshot(c,4)
                    if hook:hook()
                    dump=command(self.sql_client('mysqldump','--single-transaction','--quick','--skip-lock-tables','--routines','--events','--triggers',
                        '--hex-blob','--tz-utc','--default-character-set=utf8mb4','--set-gtid-purged=OFF','--no-tablespaces','--column-statistics=0',
                        '--skip-comments','--skip-dump-date','--skip-add-locks','--skip-add-drop-table','--complete-insert','--order-by-primary',SOURCE),seconds=max(.01,SECONDS-(time.monotonic()-start)))
                    require(self.snapshot(c,4)==before,'BACKUP_CONCURRENT_DRIFT')
                    require(time.monotonic()-start<SECONDS,'BACKUP_TIMEOUT')
                finally:
                    with c.cursor() as q:q.execute('UNLOCK TABLES')
            identity='backup-'+uuid4().hex;dump+=('-- MOSA2_BACKUP_COMPLETE:'+identity+'\n').encode();state=state_bytes(before)
            manifest=dict(format=FORMAT,backup_id=identity,database=SOURCE,schema_version=4,mysql_version=before['evidence']['properties']['version'],server_uuid=self.uuid,commit=self.commit,
                dump_sha256=sha(dump),state_sha256=sha(state),migrations=before['evidence']['ledger'],
                table_sha256={t:sha(canonical(rows)) for t,rows in before['rows'].items()},consistency='GLOBAL_READ_LOCK_HELD_FOR_FULL_EXPORT')
            seal(root,manifest,dump,state,password,signing_key)
            checked,returned,restored=unseal(root,password,signing_key.public_key(),commit=self.commit,server_uuid=self.uuid)
            require(checked==manifest and returned==dump and restored==before,'BACKUP_ENCRYPTED_READBACK_REJECTED')
            return {'status':'BACKUP_VERIFIED','backup_id':identity}
        except Exception as e:
            # Incomplete output is never a backup. No retry, no client/SQL/row diagnostics.
            for name in ('backup.sealed.json','manifest.json','mosa2-web-backup.sealed.json','mosa2-web-before.json'):
                (root/name).unlink(missing_ok=True)
            raise Rejected(e.args[0] if isinstance(e,Rejected) else 'BACKUP_ABORTED') from None

    def restore(self,root,password,public_key,target):
        require(target in TARGETS,'RESTORE_TARGET_REJECTED')
        m,dump,expected=unseal(root,password,public_key,commit=self.commit,server_uuid=self.uuid)
        # Full authentication and actual server proof BEFORE creating the fresh target/claim.
        with self.connect() as c:
            identity=self.guard(c);self.visibility(c)
            require(identity['version']==m['mysql_version'],'RESTORE_MYSQL_VERSION_REJECTED')
            with c.cursor() as q:
                q.execute('SELECT SCHEMA_NAME FROM information_schema.schemata WHERE SCHEMA_NAME=%s',(target,))
                require(q.fetchone() is None,'RESTORE_TARGET_EXISTS')
            claim=private(root,True)/('restore-'+target+'.claim')
            try:
                with claim.open('xb') as f:os.chmod(f.name,0o600);f.write(canonical(dict(target=target,server_uuid=self.uuid,backup_id=m['backup_id'])))
            except FileExistsError:raise Rejected('RESTORE_ALREADY_ATTEMPTED') from None
            try:
                with c.cursor() as q:q.execute('CREATE DATABASE '+qi(target)+' CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
                command(self.sql_client('mysql','--binary-mode=1','--skip-reconnect','--connect-timeout=3','--default-character-set=utf8mb4',"--init-command=SET SESSION time_zone='+00:00'",target),input_bytes=dump,limit=65536)
            except Exception as e:
                if isinstance(e,Rejected) and e.args[0]=='PROCESS_SQL_FAILED':
                    code=e.args[1] if len(e.args)>1 else None
                    reason={1064:'RESTORE_SQL_SYNTAX_REJECTED',1142:'RESTORE_SQL_SCOPE_REJECTED',1044:'RESTORE_DATABASE_SCOPE_REJECTED',
                        1419:'RESTORE_ROUTINE_PRIVILEGES_REJECTED',1227:'RESTORE_DEFINER_PRIVILEGES_REJECTED'}.get(code,'RESTORE_SQL_REJECTED')
                    return {'status':'RESTORE_PARTIAL_FAILED','retry_allowed':False,'failure_code':reason}
                return {'status':'RESTORE_OUTCOME_UNKNOWN','retry_allowed':False}
        try:
            # New connection after the mysql client exits, never an in-process count-only check.
            with self.database(target) as read:
                with read.cursor() as q:q.execute('FLUSH TABLES WITH READ LOCK')
                try:actual=self.snapshot(read,4)
                finally:
                    with read.cursor() as q:q.execute('UNLOCK TABLES')
            for section in ('schema_version','rows','metadata','evidence','objects'):
                require(actual[section]==expected[section],'RESTORE_MISMATCH_'+section.upper())
            return {'status':'RESTORE_READBACK_PASS','retry_allowed':False,'tables':len(actual['rows'])}
        except Exception as e:
            code=e.args[0] if isinstance(e,Rejected) and e.args and re.fullmatch('[A-Z_]+',str(e.args[0])) else 'RESTORE_VALIDATION_REJECTED'
            return {'status':'RESTORE_VERIFICATION_FAILED','retry_allowed':False,'failure_code':code}
