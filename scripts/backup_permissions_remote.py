"""Exactly one read-only metadata inspection; existing pinned SSH/tunnel and DB identity."""
import json,logging,os,subprocess,sys,shutil,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collector_actions as access

def execute(env,paramiko):
    if env.get('GITHUB_RUN_ATTEMPT')!='1':return {'status':'FIRST_ATTEMPT_ONLY'}
    try:
        config=access.configuration(env)
        logging.getLogger('paramiko').disabled=True
        with access.ssh_client(config,{},paramiko) as transport:
            with access.tunnel(transport,{}) as port:
                scope=env.get('BACKUP_INSPECTION_SCOPE','permissions')
                if scope not in ('permissions','schema6-prepare'):raise ValueError()
                request=dict(password=env['MOSA_TEST_DB_PASSWORD'],port=port,attempt=env['GITHUB_RUN_ATTEMPT'],scope=scope)
                child={k:env[k] for k in ('PATH','HOME','LANG') if k in env}
                p=subprocess.run(['php',str(ROOT/'scripts/backup_permissions.php')],input=json.dumps(request),
                    text=True,capture_output=True,env=child,timeout=60)
                if p.stderr or len(p.stdout)>16384:raise ValueError()
                result=json.loads(p.stdout)
                if p.returncode and result.get('status')=='BACKUP_PERMISSIONS_INSPECTED':raise ValueError()
                if scope=='schema6-prepare' and result.get('status')=='BACKUP_PERMISSIONS_INSPECTED':
                    # Probe the runner client only; never run a dump or contact the DB.
                    client=shutil.which('mysqldump')
                    probe=subprocess.run([client,'--no-defaults','--version'],text=True,capture_output=True,timeout=5) if client else None
                    result['runner_export_tools']={
                        'mysql8_client_identified':bool(probe and probe.returncode==0 and not probe.stderr and
                            re.search(r'(?:Ver|Distrib) 8\.0\.',probe.stdout)),
                        'scratch_free_bytes':shutil.disk_usage(env['RUNNER_TEMP']).free,
                        'export_space_sufficiency':'NOT_PROVEN_WITHOUT_FULL_SIZE_AND_ENCRYPTION_BOUNDS',
                        'private_key_custody':'NOT_PROVEN'}
                return result
    except Exception:return {'status':'PERMISSIONS_ACCESS_OR_PROCESS_REJECTED'}

if __name__=='__main__':
    import paramiko
    report=execute(os.environ,paramiko)
    print(json.dumps(report))
    sys.exit(0 if report.get('status')=='BACKUP_PERMISSIONS_INSPECTED' else 1)
