"""Future explicitly authorized Actions backup/isolated restore. Not run by offline CI."""
import json,logging,os,sys
from pathlib import Path
from scripts import database_backup as b
from scripts import database_backup_scoped as scoped

def run(env,request,isolated_engine):
    # All no-source prerequisites precede even SSH configuration/preflight.
    b.require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_RUN_ATTEMPT')=='1','FIRST_ATTEMPT_ACTIONS_ONLY')
    commit=env.get('GITHUB_SHA','');root=Path(env['RUNNER_TEMP'])/'mosa2-db-backup-private'
    b.require(request.get('authorization')=='MOSA2-DB-BACKUP-ONCE:'+commit,'EXPLICIT_BACKUP_AUTHORIZATION_REQUIRED')
    key_text=env.get(scoped.SECRET_NAME,'')
    scoped.recovery(key_text)
    root.mkdir(mode=0o700,exist_ok=False)
    scoped.pre_export(root,key_text,request['quiescence'],commit,storage_confirmed=request.get('private_artifact_storage_confirmed'),
        retention_days=request.get('retention_days'))
    from datetime import datetime,timezone
    clock=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')
    engine=isolated_engine(commit,clock)
    with engine.connect() as c:
        engine.guard(c);engine.visibility(c)
        with c.cursor() as q:
            q.execute('SELECT SCHEMA_NAME FROM information_schema.schemata WHERE SCHEMA_NAME=%s',('mosa2_restore_isolated_a',))
            b.require(q.fetchone() is None,'RESTORE_TARGET_EXISTS')
    from scripts import backup_permissions_remote as preflight
    from scripts import collector_actions as access
    from scripts.database_backup_live import LiveSource
    import paramiko
    logging.getLogger('paramiko').disabled=True
    report=preflight.execute(dict(env,BACKUP_INSPECTION_SCOPE='schema6-prepare'),paramiko)
    scoped.prerequisites(report)
    config=access.configuration(env)
    with access.ssh_client(config,{},paramiko) as ssh:
        with access.tunnel(ssh,{}) as port:
            source=LiveSource(env,port,report,clock)
            scoped.export(source,root,key_text,request['quiescence'],commit,
                storage_confirmed=True,retention_days=request['retention_days'])
            source_uuid=source.uuid
    # Restore factory is supplied only by the existing guarded ephemeral CI service.
    result=scoped.restore(engine,root,key_text,source_uuid,'mosa2_restore_isolated_a')
    b.require(result['status']=='BACKUP_RESTORE_PASS','SCOPED_RESTORE_REJECTED')
    return result

def guarded_service(commit,clock):
    # Existing ephemeral connection factory/account; never a hosting account.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
    from test_collector_persistence_mysql import connect
    from test_database_backup_mysql import BackupMySQLTests
    def evidence(database,version):
        raw=b.command(['php',str(Path(__file__).resolve().parents[1]/'tests/backup_restore_mysql.php')],
            input_bytes=json.dumps(dict(database=database,version=version,now=clock)).encode(),limit=b.STATE_LIMIT)
        reply=json.loads(raw);b.require(reply.get('ok') is True,'RESTORE_EVIDENCE_REJECTED');return reply['result']
    engine=b.IsolatedBackup(connect,evidence,commit)
    with connect() as c:engine.guard(c)
    fixture=BackupMySQLTests('test_basis_restore');fixture.engine=engine;fixture.restore_account()
    return engine
if __name__=='__main__':
    try:
        request=json.loads(sys.stdin.read(16385))
        result=run(os.environ,request,guarded_service)
    except Exception as error:
        safe={'RECOVERY_KEY_REQUIRED','QUIESCENCE_PROOF_REQUIRED','QUIESCENCE_PROOF_REJECTED',
            'PRIVATE_RETENTION_REQUIRED','BACKUP_RESOURCES_REJECTED','FIRST_ATTEMPT_ACTIONS_ONLY',
            'EXPLICIT_BACKUP_AUTHORIZATION_REQUIRED','SOURCE_SCHEMA_REJECTED','SOURCE_IDENTITY_REJECTED',
            'SOURCE_RIGHTS_REJECTED','SOURCE_VISIBILITY_REJECTED','SOURCE_ROUTINES_UNSUPPORTED',
            'SOURCE_WRITER_SIGNAL_REJECTED','BACKUP_CONCURRENT_DRIFT','SCOPED_EXPORT_REJECTED','SCOPED_RESTORE_REJECTED'}
        code=error.args[0] if isinstance(error,b.Rejected) and error.args and error.args[0] in safe else 'BACKUP_ONCE_STOPPED_NO_RETRY'
        result={'status':code,'retry_allowed':False}
    print(json.dumps(result))
    sys.exit(0 if result.get('status')=='BACKUP_RESTORE_PASS' else 1)
