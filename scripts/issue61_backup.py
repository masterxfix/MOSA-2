"""Issue #61 only: read-lock, export, privately store, and prove a Schema 6 restore.

This command has no live restore or live data mutation path. The existing
provider-free SSH profile is reused; replay is confined to a networkless container.
"""
import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import time

from scripts import database_backup as backup
from scripts import database_backup_scoped as scoped
import collector_actions as access

DB = backup.SOURCE
PRIVATE = '/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector'
TARGET = 'mosa2_restore_isolated_a'
KEY_ENV = 'MOSA2_ISSUE61_BACKUP_RECOVERY_KEY'
CONTEXT = b'mosa2-issue61-schema6-backup'
ROW_LIMIT = 20000
LOCK_SECONDS = 330


def require(condition, code):
    backup.require(condition, code)


def query(db, sql, args=None):
    with db.cursor() as cursor:
        cursor.execute(sql, args)
        return cursor.fetchall() if cursor.description else None


def scalar(db, sql):
    return query(db, sql)[0][0]


def tables(db):
    return query(db, 'SELECT TABLE_NAME,TABLE_TYPE,ENGINE FROM information_schema.TABLES '
                     'WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')


def capture(db, expected):
    """Complete structure, all PK-ordered values, and full identity-independent digests."""
    require(tables(db) == tuple((t, 'BASE TABLE', 'InnoDB') for t in expected), 'TABLE_CONTRACT')
    for kind, column in [('TRIGGERS', 'TRIGGER_SCHEMA'), ('EVENTS', 'EVENT_SCHEMA'), ('ROUTINES', 'ROUTINE_SCHEMA')]:
        require(scalar(db, f'SELECT COUNT(*) FROM information_schema.{kind} WHERE {column}=DATABASE()') == 0,
                'UNEXPECTED_SCHEMA_OBJECT')
    result = {}
    size = 0
    for name in expected:
        table = backup.qi(name)
        ddl = query(db, 'SHOW CREATE TABLE ' + table)[0][1]
        primary = sorted(query(db, 'SHOW INDEX FROM ' + table + " WHERE Key_name='PRIMARY'"), key=lambda r:r[3])
        require(bool(primary), 'PRIMARY_KEY_REQUIRED')
        order = ','.join(backup.qi(row[4]) for row in primary)
        data = query(db, f'SELECT * FROM {table} ORDER BY {order} LIMIT {ROW_LIMIT + 1}')
        require(len(data) <= ROW_LIMIT, 'BACKUP_ROW_LIMIT')
        encoded = backup.canonical([[backup.value(v) for v in row] for row in data])
        size += len(encoded)
        require(size < backup.STATE_LIMIT, 'BACKUP_STATE_LIMIT')
        result[name] = dict(rows=len(data), data_sha256=backup.sha(encoded),
                            ddl_sha256=backup.sha(ddl.encode()),
                            schema_sha256=backup.sha(re.sub(r' AUTO_INCREMENT=\d+\b','',ddl).encode()))
    return result


def source_connection(port, env):
    import pymysql
    return pymysql.connect(host='127.0.0.1',port=port,user=DB,password=env['MOSA_TEST_DB_PASSWORD'],
        database=DB,autocommit=True,connect_timeout=6,read_timeout=25,write_timeout=10,charset='utf8mb4',
        init_command="SET SESSION time_zone='+00:00', lock_wait_timeout=5, innodb_lock_wait_timeout=5")


def source_identity(db):
    (name, user, version, port, uuid, role, fks) = query(db,
        'SELECT DATABASE(), CURRENT_USER(), VERSION(), @@port, @@server_uuid, CURRENT_ROLE(), @@foreign_key_checks')[0]
    require((name,user,version,port,role,fks)==(DB,DB+'@localhost','8.0.26-16',3307,'NONE',1)
        and re.fullmatch('[0-9a-f-]{36}',uuid), 'SOURCE_IDENTITY')
    grants={r[0] for r in query(db,'SHOW GRANTS')}
    require(grants=={'GRANT USAGE ON *.* TO \x60h29077_mosa2_test\x60@\x60localhost\x60',
        'GRANT ALL PRIVILEGES ON \x60h29077\\_mosa2\\_test\x60.* TO \x60h29077_mosa2_test\x60@\x60localhost\x60'},
        'SOURCE_GRANTS')
    return uuid


def guarded_inventory(db, expected, audited):
    require(tables(db) == tuple((t,'BASE TABLE','InnoDB') for t in expected), 'TABLE_CONTRACT')
    require(scalar(db, 'SELECT COUNT(*) FROM m2_jobs WHERE enabled=1')==0
        and scalar(db, "SELECT COUNT(*) FROM m2_job_runs WHERE status='running'")==0, 'ACTIVE_DB_JOB')
    require(scalar(db,'SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID<>CONNECTION_ID()')==0,
            'OTHER_DB_ACCOUNT_CONNECTION')
    checksums = query(db,'SELECT version,LOWER(HEX(checksum)) FROM m2_schema_migrations ORDER BY version')
    require(checksums==tuple(enumerate(audited,1)), 'MIGRATION_LEDGER')


def dump_with_lock(port, env, expected, audited):
    client=shutil.which('mysqldump')
    require(client is not None and re.search(rb'(?:Ver|Distrib) 8\.0\.',
        backup.command([client,'--no-defaults','--version'],limit=4096)), 'MYSQL_8_CLIENT_REQUIRED')
    with closing(source_connection(port,env)) as db:
        uuid=source_identity(db)
        guarded_inventory(db,expected,audited)
        query(db,'LOCK TABLES '+','.join(backup.qi(name)+' READ' for name in expected))
        try:
            started=time.monotonic()
            before=capture(db,expected)
            dump=backup.command([client,'--defaults-file=/dev/stdin',*scoped.FLAGS,DB],
                input_bytes=scoped.client_input(port,env['MOSA_TEST_DB_PASSWORD']),
                environment={'PATH':env['PATH'],'LANG':'C.UTF-8','MYSQL_TEST_LOGIN_FILE':'/dev/null'},
                seconds=max(1,LOCK_SECONDS-(time.monotonic()-started)))
            require(len(dump)>0 and capture(db,expected)==before and time.monotonic()-started<LOCK_SECONDS,
                    'LIVE_SNAPSHOT_DRIFT')
        finally:
            query(db,'UNLOCK TABLES')
    return uuid, before, dump


def seal(key, manifest, dump):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    metadata=backup.canonical(manifest)
    nonce=os.urandom(12)
    ciphertext=nonce+AESGCM(key).encrypt(nonce,dump,CONTEXT+metadata)
    return ciphertext,metadata


def read_sealed(key, envelope, metadata, expected):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    require(metadata==backup.canonical(expected) and len(envelope)<=backup.DUMP_LIMIT+28,'MANIFEST_REJECTED')
    dump=AESGCM(key).decrypt(envelope[:12],envelope[12:],CONTEXT+metadata)
    require(backup.sha(dump)==expected['dump_sha256'],'BACKUP_HASH_REJECTED')
    return dump


def safe_directory(sftp, name):
    info=sftp.lstat(name)
    require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode)==0o700 and sftp.normalize(name)==name,
            'PRIVATE_STORAGE_REJECTED')
    return info.st_uid


def store_and_reopen(sftp, run_id, key, manifest, dump):
    root=PRIVATE+'/issue61-backup-'+run_id
    owner=safe_directory(sftp,PRIVATE)
    sftp.mkdir(root,0o700)  # refuse reuse
    require(safe_directory(sftp,root)==owner,'PRIVATE_OWNER_REJECTED')
    cipher, meta=seal(key,manifest,dump)
    def put_read(name,data):
        path=root+'/'+name
        with sftp.open(path,'wx') as stream:
            stream.chmod(0o600)
            stream.write(data)
        info=sftp.lstat(path)
        require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode)==0o600
            and info.st_uid==owner and info.st_size==len(data),'PRIVATE_FILE_REJECTED')
        with sftp.open(path,'rb') as stream:
            restored=stream.read(len(data)+1)
        require(backup.sha(restored)==backup.sha(data),'PRIVATE_READBACK_REJECTED')
        return restored
    cipher_back=put_read('backup.aesgcm',cipher)
    meta_back=put_read('manifest.json',meta)
    return read_sealed(key,cipher_back,meta_back,manifest),backup.sha(cipher_back),backup.sha(meta_back)


def isolated_restore(dump, expected, env):
    """Docker's none network and a Unix socket are the sole destination."""
    name='mosa2-issue61-'+env['GITHUB_RUN_ID']
    container=backup.command(['docker','run','--detach','--name',name,'--network=none','--tmpfs',
        '/var/lib/mysql:rw,nosuid,nodev,size=512m','-e','MYSQL_ALLOW_EMPTY_PASSWORD=yes',
        '-e','MYSQL_DATABASE='+TARGET,'mysql:8.0.46','--event-scheduler=OFF']).decode().strip()
    require(re.fullmatch('[0-9a-f]{64}',container),'ISOLATION_CONTAINER_REJECTED')
    mysql=['docker','exec','-i',container,'mysql','--no-defaults','--protocol=socket','--user=root',
           '--default-character-set=utf8mb4','--binary-mode=1','--batch','--skip-column-names',TARGET]
    try:
        require(backup.command(['docker','inspect','--format','{{.HostConfig.NetworkMode}}',container]).strip()==b'none',
                'ISOLATION_NETWORK_REJECTED')
        for _ in range(60):
            try:
                ident=backup.command(mysql,input_bytes=b'SELECT DATABASE(),@@port,@@event_scheduler,@@skip_networking,VERSION();',
                    limit=4096,seconds=5).decode().strip().split('\t')
                if ident[:4]==[TARGET,'3306','OFF','0'] and ident[4].startswith('8.0.46'):
                    break
            except backup.Rejected:
                pass
            time.sleep(1)
        else:
            raise backup.Rejected('ISOLATED_MYSQL_NOT_READY')
        backup.command(mysql,input_bytes=dump,limit=4096,seconds=90)
        # Re-export independently with the same options, then compare every DDL
        # and row. Client-version boilerplate is outside the DDL/row sections.
        roundtrip=backup.command(['docker','exec',container,'mysqldump','--no-defaults','--protocol=socket',
            '--user=root',*scoped.FLAGS,TARGET],seconds=90)
        def ddl_and_rows(sql):
            return b'\n'.join(line for line in sql.split(b'\n')
                if line and not line.startswith((b'/*!',b'--',b'/*')))
        require(ddl_and_rows(roundtrip)==ddl_and_rows(dump),'ISOLATED_DUMP_MISMATCH')
        counts=backup.command(mysql,input_bytes=(';'.join('SELECT COUNT(*) FROM '+backup.qi(t) for t in expected)+';').encode(),
                             limit=4096).decode().splitlines()
        require([int(c) for c in counts]==[t['rows'] for t in expected.values()],'ISOLATED_ROWCOUNT_MISMATCH')
    finally:
        backup.command(['docker','rm','--force',container],limit=4096,seconds=20)


def run(env):
    import paramiko
    logging.getLogger('paramiko').disabled=True
    report={'ok':False,'database_writes':0,'provider_requests':0,'isolated_restore':'NOT_STARTED'}
    stage='authorization'
    try:
        sha=env['GITHUB_SHA']; run_id=env['GITHUB_RUN_ID']
        require(env['GITHUB_REPOSITORY']=='masterxfix/MOSA-2' and env['GITHUB_ACTIONS']=='true'
            and env['GITHUB_EVENT_NAME']=='workflow_dispatch' and env['GITHUB_RUN_ATTEMPT']=='1'
            and env['GITHUB_REF']=='refs/heads/codex/issue-61-controlled-reset'
            and env['ISSUE61_BACKUP_AUTH']=='MOSA2-ISSUE61-BACKUP:'+sha and re.fullmatch('[0-9a-f]{40}',sha)
            and re.fullmatch('[0-9]{6,20}',run_id),'BACKUP_AUTHORIZATION')
        stage='key'
        raw=env.get(KEY_ENV,'')
        scoped.recovery(raw)  # independent 256-bit backup recovery material
        key=bytes.fromhex(raw)
        stage='schema_contract'
        php="require 'scripts/market_collector/schema6.php'; echo json_encode(\\Mosa2\\CollectorSchema5\\envelope(6),JSON_THROW_ON_ERROR);"
        contract=json.loads(backup.command(['php','-r',php],limit=20000))
        require(len(contract['tables'])==26 and len(contract['digests'])==6,'SCHEMA6_CONTRACT')
        stage='source_read_locked_export'
        with access.ssh_client(access.configuration(env),report,paramiko) as ssh:
            with access.tunnel(ssh,report) as port:
                uuid, tables_before, dump=dump_with_lock(port,env,contract['tables'],contract['digests'])
            report['tables']=len(tables_before)
            stage='private_dogado_readback'
            now=datetime.now(timezone.utc)
            manifest=dict(format='MOSA2-ISSUE61-AES256-GCM',database=DB,schema=6,source_uuid=uuid,
                commit=sha,run_id=run_id,created_utc=now.isoformat(),delete_by_utc=(now+timedelta(days=7)).isoformat(),
                dump_sha256=backup.sha(dump),table_manifest=tables_before)
            with paramiko.SFTPClient.from_transport(ssh) as sftp:
                dump, cipher_sha, manifest_sha=store_and_reopen(sftp,run_id,key,manifest,dump)
            report.update(private_cipher_sha256=cipher_sha,private_manifest_sha256=manifest_sha,
                          dump_sha256=manifest['dump_sha256'],delete_by_utc=manifest['delete_by_utc'])
        stage='isolated_restore'
        isolated_restore(dump,tables_before,env)
        report.update(ok=True,isolated_restore='PASS')
    except Exception as error:
        # Provider, SQL, filesystem and decryption diagnostics are private.
        reason=error.args[0] if isinstance(error,backup.Rejected) and error.args else ''
        report.update(stage=stage,reason=reason if isinstance(reason,str) and re.fullmatch('[A-Z0-9_]{1,80}',reason) else 'OPERATION_STOPPED')
    return report


if __name__=='__main__':
    report=run(os.environ)
    rendered=access.public_text(report,os.environ)
    if os.environ.get(KEY_ENV) and os.environ[KEY_ENV] in rendered:
        rendered='{"ok":false,"reason":"SECRET_OUTPUT_BLOCKED"}'
    print(rendered)
    sys.exit(0 if json.loads(rendered)['ok'] else 1)
