"""Narrow future MOSA2 schema4 export. No live entrypoint or automatic activation.
The caller supplies the existing verified readonly source and an authoritative
short-lived quiescence assertion; the CI executor's isolation guards are unchanged.
"""
import base64,hashlib,json,os,re,shutil,time
from pathlib import Path
from uuid import uuid4
from scripts import database_backup as b

FLAGS=('--single-transaction','--quick','--skip-lock-tables','--no-tablespaces',
 '--set-gtid-purged=OFF','--hex-blob','--tz-utc','--skip-routines','--events','--triggers',
 '--default-character-set=utf8mb4','--column-statistics=0','--skip-comments',
 '--skip-dump-date','--skip-add-locks','--skip-add-drop-table','--complete-insert','--order-by-primary')
SECRET_NAME='MOSA_TEST_DB_BACKUP_RECOVERY_KEY'
def recovery(text):
    b.require(isinstance(text,str) and re.fullmatch('[0-9a-f]{64}',text) and len(set(text))>=8,'RECOVERY_KEY_REQUIRED')
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    # Independent recovery material, never a hosting/DB password. Separate signing domain.
    seed=HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=b'mosa2-db-backup-ed25519-v1').derive(bytes.fromhex(text))
    return text,Ed25519PrivateKey.from_private_bytes(seed)
def lease(document,public_key,commit,now=None):
    now=time.time() if now is None else now
    b.require(isinstance(document,dict) and set(document)=={'claim','signature'},'QUIESCENCE_PROOF_REQUIRED')
    claim=document['claim']
    b.require(set(claim)=={'purpose','database','commit','all_test_writers_stopped','ddl_prohibited','issued_at','expires_at','run_id'},'QUIESCENCE_PROOF_REQUIRED')
    try:public_key.verify(base64.b64decode(document['signature'],validate=True),b.canonical(claim))
    except Exception:raise b.Rejected('QUIESCENCE_PROOF_REJECTED') from None
    b.require(claim['purpose']=='MOSA2_SCHEMA4_BACKUP' and claim['database']==b.SOURCE and claim['commit']==commit
        and claim['all_test_writers_stopped'] is True and claim['ddl_prohibited'] is True
        and type(claim['issued_at']) is int and type(claim['expires_at']) is int
        and 0<claim['expires_at']-claim['issued_at']<=900 and claim['issued_at']<=now<claim['expires_at']
        and re.fullmatch('[a-z0-9-]{12,80}',claim['run_id']),'QUIESCENCE_PROOF_REJECTED')
    return claim
def prerequisites(report):
    b.require(report.get('status')=='BACKUP_PERMISSIONS_INSPECTED' and report.get('database_identity')=='PASS'
        and report.get('read_only_confirmed') is True,'SOURCE_IDENTITY_REJECTED')
    inv=report.get('schema6_prepare',{})
    b.require(inv.get('status')=='SCHEMA6_PREPARE_INVENTORY_PASS' and inv.get('schema_version')==4
        and inv.get('table_count')==17 and inv.get('exact_structure')=='PASS' and inv.get('ledger_checksums')=='PASS'
        and inv.get('all_innodb') is True,'SOURCE_SCHEMA_REJECTED')
    b.require(report.get('complete_object_visibility')=='JA','SOURCE_VISIBILITY_REJECTED')
    b.require(report.get('objects',{}).get('ROUTINE',{}).get('visible_count')==0,'SOURCE_ROUTINES_UNSUPPORTED')
    b.require(all(report.get('rights',{}).get(r) is True for r in ('SELECT','SHOW VIEW','TRIGGER','EVENT')),'SOURCE_RIGHTS_REJECTED')
    b.require(inv.get('enabled_jobs')=='0' and inv.get('running_jobs')=='0' and inv.get('other_schema_sessions_visible')==0
        and not any(inv.get('named_locks_in_use',{'missing':True}).values()),'SOURCE_WRITER_SIGNAL_REJECTED')
def client_input(port,password):
    b.require(type(port) is int and 1<=port<=65535 and isinstance(password,str) and 0<len(password)<=4096
        and not any(c in password for c in '\x00\r\n'),'SOURCE_CREDENTIAL_REJECTED')
    escaped=password.replace('\\','\\\\').replace('"','\\"')
    return ('[client]\nhost=127.0.0.1\nprotocol=tcp\nport='+str(port)+'\nuser=h29077_mosa2_test\npassword="'+escaped+'"\n').encode()
def run_dump(executable,port,password):
    b.require(os.name=='posix' and Path('/dev/stdin').exists(),'PRIVATE_STDIN_CLIENT_REQUIRED')
    argv=[executable,'--defaults-file=/dev/stdin',*FLAGS,b.SOURCE]
    # Password travels through private anonymous stdin, never argv/environment/persisted config.
    return b.command(argv,input_bytes=client_input(port,password),environment={
        'PATH':os.environ.get('PATH','/usr/bin:/bin'),'LANG':'C.UTF-8','MYSQL_TEST_LOGIN_FILE':'/dev/null'})
def pre_export(root,key_text,document,commit,*,storage_confirmed,retention_days,free_bytes=None):
    password,key=recovery(key_text);claim=lease(document,key.public_key(),commit)
    b.require(re.fullmatch('[0-9a-f]{40}',commit),'BACKUP_COMMIT_REQUIRED')
    b.require(storage_confirmed is True and type(retention_days) is int and 1<=retention_days<=7,'PRIVATE_RETENTION_REQUIRED')
    root=b.private(root,True)
    free=shutil.disk_usage(root).free if free_bytes is None else free_bytes
    # Worst-case existing finite dump/state/envelope, crypto work buffers and scratch.
    b.require(type(free) is int and free>=8*(b.DUMP_LIMIT+b.STATE_LIMIT+b.FILE_LIMIT),'BACKUP_RESOURCES_REJECTED')
    b.require(not any((root/n).exists() for n in ('export.claim','backup.sealed.json','manifest.json')),'EXPORT_ALREADY_ATTEMPTED')
    return password,key,claim
def export(source,root,key_text,document,commit,*,storage_confirmed,retention_days):
    password,key,claim=pre_export(root,key_text,document,commit,storage_confirmed=storage_confirmed,retention_days=retention_days)
    root=Path(root)
    # Claim before any provider-free source access. Failures never reuse this root.
    with (root/'export.claim').open('xb') as f:os.chmod(f.name,0o600);f.write(b.canonical({'run_id':claim['run_id'],'commit':commit}))
    try:
        report=source.permissions();prerequisites(report);lease(document,key.public_key(),commit)
        before=source.snapshot()
        b.require(before['schema_version']==4 and not any(k.startswith(('PROCEDURE:','FUNCTION:')) for k in before['objects']),'SOURCE_ROUTINES_UNSUPPORTED')
        b.require(sorted(before['rows'])==b.migration.contract()['envelope4']['tables'],'BACKUP_TABLE_SET_REJECTED')
        dump=source.dump()
        lease(document,key.public_key(),commit)
        b.require(source.snapshot()==before,'BACKUP_CONCURRENT_DRIFT')
        identity='backup-'+uuid4().hex;dump+=('-- MOSA2_BACKUP_COMPLETE:'+identity+'\n').encode();state=b.state_bytes(before)
        manifest=dict(format=b.FORMAT,backup_id=identity,database=b.SOURCE,schema_version=4,
            mysql_version=before['evidence']['properties']['version'],server_uuid=source.uuid,commit=commit,
            dump_sha256=b.sha(dump),state_sha256=b.sha(state),migrations=before['evidence']['ledger'],
            table_sha256={t:b.sha(b.canonical(rows)) for t,rows in before['rows'].items()},
            consistency='SIGNED_SHORT_LIVED_CONTROLLED_SCHEMA_QUIESCENCE')
        b.seal(root,manifest,dump,state,password,key)
        actual=b.unseal(root,password,key.public_key(),commit=commit,server_uuid=source.uuid)
        b.require(actual==(manifest,dump,before),'BACKUP_ENCRYPTED_READBACK_REJECTED')
        lease(document,key.public_key(),commit)
        return {'status':'BACKUP_VERIFIED','backup_id':identity}
    except Exception as e:
        for name in ('backup.sealed.json','manifest.json','mosa2-web-backup.sealed.json','mosa2-web-before.json'):
            (root/name).unlink(missing_ok=True)
        known={'SOURCE_IDENTITY_REJECTED','SOURCE_SCHEMA_REJECTED','SOURCE_VISIBILITY_REJECTED','SOURCE_ROUTINES_UNSUPPORTED',
            'SOURCE_RIGHTS_REJECTED','SOURCE_WRITER_SIGNAL_REJECTED','BACKUP_CONCURRENT_DRIFT','QUIESCENCE_PROOF_REJECTED',
            'PROCESS_TIMEOUT','PROCESS_CONNECTION_LOST','PROCESS_OUTPUT_REJECTED','BACKUP_SIZE_LIMIT'}
        raise b.Rejected(e.args[0] if isinstance(e,b.Rejected) and e.args[0] in known else 'SCOPED_EXPORT_REJECTED') from None
def restore(engine,root,key_text,source_uuid,target):
    password,key=recovery(key_text)
    # engine is the original isolated executor, with unchanged constructor/server guards.
    b.require(type(engine) is b.IsolatedBackup,'ISOLATED_RESTORE_REQUIRED')
    result=engine.restore_external(root,password,key.public_key(),target,source_uuid)
    b.require(result['status']=='RESTORE_READBACK_PASS','SCOPED_RESTORE_REJECTED')
    return {'status':'BACKUP_RESTORE_PASS','tables':result['tables'],'retry_allowed':False}
