"""Future Actions-only source binding; fixed existing tunnel, account and schema.
Importing this module never connects. No source DDL/DML, lock, retry or provider.
"""
import contextlib,json,os,re,time
from datetime import datetime,timezone
from pathlib import Path
from scripts import database_backup as b
from scripts import database_backup_scoped as scoped

class LiveSource:
    def __init__(self,env,port,report,now=None):
        self.env=env;self.port=port;self.report=report;self.uuid=None;self.checked=time.monotonic()
        self.now=now or datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')
    def permissions(self):
        b.require(time.monotonic()-self.checked<180,'SOURCE_PREFLIGHT_EXPIRED')
        return self.report
    @contextlib.contextmanager
    def connection(self):
        import pymysql
        with pymysql.connect(host='127.0.0.1',port=self.port,user=b.SOURCE,password=self.env['MOSA_TEST_DB_PASSWORD'],
                database=b.SOURCE,charset='utf8mb4',cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,connect_timeout=5,read_timeout=15,write_timeout=5) as c:
            self.visibility(c)
            with c.cursor() as q:q.execute("SET SESSION time_zone='+00:00'");q.execute('SET SESSION max_execution_time=10000')
            yield c
    def visibility(self,c):
        with c.cursor() as q:
            q.execute('SELECT DATABASE() AS db,CURRENT_USER() AS account,VERSION() AS version,@@port AS port,@@server_uuid AS uuid,CURRENT_ROLE() AS role')
            r=q.fetchone()
            b.require(r['db']==b.SOURCE and r['account']==b.SOURCE+'@localhost'
                and r['version']=='8.0.26-16' and r['port']==3307 and r['role']=='NONE','SOURCE_IDENTITY_REJECTED')
            b.require(re.fullmatch('[0-9a-f-]{36}',r['uuid']),'SOURCE_IDENTITY_REJECTED')
            if self.uuid is None:self.uuid=r['uuid']
            b.require(self.uuid==r['uuid'],'SOURCE_IDENTITY_REJECTED')
            q.execute('SHOW GRANTS FOR CURRENT_USER')
            grants={next(iter(row.values())) for row in q.fetchall()}
            expected={'GRANT USAGE ON *.* TO \x60h29077_mosa2_test\x60@\x60localhost\x60',
                'GRANT ALL PRIVILEGES ON \x60h29077\\_mosa2\\_test\x60.* TO \x60h29077_mosa2_test\x60@\x60localhost\x60'}
            b.require(grants==expected,'SOURCE_RIGHTS_REJECTED')
        c.rollback()
    def evidence(self,database,version):
        b.require(database==b.SOURCE and version==4,'DATABASE_SCOPE_REJECTED')
        wire=json.dumps(dict(password=self.env['MOSA_TEST_DB_PASSWORD'],port=self.port,now=self.now)).encode()
        raw=b.command(['php',str(Path(__file__).with_name('database_backup_read.php'))],
            input_bytes=wire,limit=b.STATE_LIMIT,seconds=150,environment={k:self.env[k] for k in ('PATH','HOME','LANG') if k in self.env})
        result=json.loads(raw);b.require(result.get('ok') is True,'SOURCE_EVIDENCE_REJECTED')
        return result['result']
    def snapshot(self):
        with self.connection() as c:
            return b.capture_snapshot(c,4,self.visibility,self.evidence,b.capture_objects)
    def dump(self):
        import shutil
        client=shutil.which('mysqldump');b.require(client is not None,'MYSQL8_CLIENT_REQUIRED')
        version=b.command([client,'--no-defaults','--version'],limit=4096)
        b.require(re.search(rb'(?:Ver|Distrib) 8\.0\.',version),'MYSQL8_CLIENT_REQUIRED')
        return scoped.run_dump(client,self.port,self.env['MOSA_TEST_DB_PASSWORD'])
