"""One bounded readonly inspection over the existing pinned SSH/tunnel."""
import json,logging,os,subprocess,sys,shutil,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import collector_actions as access

PHASES=frozenset({
    'PERMISSIONS_CONNECTION_OR_IDENTITY_REJECTED','PERMISSIONS_GRANTS_REJECTED',
    'PERMISSIONS_OBJECT_METADATA_REJECTED','SCHEMA6_PREPARE_INVENTORY_REJECTED',
    'READ_ONLY_REJECTED','ARTIFACT_LOAD_REJECTED','TABLE_SET_REJECTED','STRUCTURE_REJECTED',
    'LEDGER_REJECTED','COUNTS_REJECTED','PROVENANCE_REJECTED','JOB_STATUS_REJECTED','REPORT_REJECTED',
})
def phase(stderr,scope):
    """Strict whole-stream allowlist; do not return or publish arbitrary stderr."""
    if isinstance(stderr,bytes):
        stderr=stderr.decode('ascii',errors='strict')
    if not isinstance(stderr,str) or len(stderr)>4096:raise ValueError()
    if scope=='permissions':
        if stderr:raise ValueError()
        return None
    last=None
    for marker in stderr.splitlines(keepends=True):
        if not marker.endswith('\n') or not marker.startswith('MOSA2_PHASE:'):raise ValueError()
        code=marker[len('MOSA2_PHASE:'):-1]
        if code not in PHASES:raise ValueError()
        last=code
    return last

def execute(env,paramiko):
    if env.get('GITHUB_RUN_ATTEMPT')!='1':return {'status':'FIRST_ATTEMPT_ONLY'}
    stage='CONFIGURATION';scope='permissions';seconds=60
    try:
        scope=env.get('BACKUP_INSPECTION_SCOPE','permissions')
        if scope not in ('permissions','schema6-prepare'):raise ValueError()
        # 17 tables: >119 complete metadata reads over the pinned tunnel.
        # Keep SQL per-query limits unchanged; cap the extensive inventory at 150s.
        seconds=150 if scope=='schema6-prepare' else 60
        config=access.configuration(env)
        logging.getLogger('paramiko').disabled=True
        stage='SSH'
        with access.ssh_client(config,{},paramiko) as transport:
            stage='TUNNEL'
            with access.tunnel(transport,{}) as port:
                request=dict(password=env['MOSA_TEST_DB_PASSWORD'],port=port,attempt=env['GITHUB_RUN_ATTEMPT'],scope=scope)
                child={k:env[k] for k in ('PATH','HOME','LANG') if k in env}
                stage='SUBPROCESS'
                p=subprocess.run(['php',str(ROOT/'scripts/backup_permissions.php')],input=json.dumps(request),
                    text=True,capture_output=True,env=child,timeout=seconds)
                stage='STDERR'
                last=phase(p.stderr,scope)
                stage='RESULT'
                if len(p.stdout)>16384:raise ValueError()
                result=json.loads(p.stdout)
                if not isinstance(result,dict):raise ValueError()
                if p.returncode and result.get('status')=='BACKUP_PERMISSIONS_INSPECTED':raise ValueError()
                if scope=='schema6-prepare':
                    result['last_phase']=last
                    result['process_limit_seconds']=seconds
                if scope=='schema6-prepare' and result.get('status')=='BACKUP_PERMISSIONS_INSPECTED':
                    stage='CLIENT_PROBE'
                    client=shutil.which('mysqldump')
                    probe=subprocess.run([client,'--no-defaults','--version'],text=True,capture_output=True,timeout=5) if client else None
                    result['runner_export_tools']={
                        'mysql8_client_identified':bool(probe and probe.returncode==0 and not probe.stderr and
                            re.search(r'(?:Ver|Distrib) 8\.0\.',probe.stdout)),
                        'scratch_free_bytes':shutil.disk_usage(env['RUNNER_TEMP']).free,
                        'export_space_sufficiency':'NOT_PROVEN_WITHOUT_FULL_SIZE_AND_ENCRYPTION_BOUNDS',
                        'private_key_custody':'NOT_PROVEN'}
                return result
    except subprocess.TimeoutExpired as error:
        if stage!='SUBPROCESS':return {'status':'PERMISSIONS_CLIENT_PROBE_REJECTED'}
        try:last=phase(error.stderr or '',scope)
        except (ValueError,UnicodeError):
            return {'status':'PERMISSIONS_STDERR_REJECTED','process_timeout':True,'process_limit_seconds':seconds}
        return {'status':'PERMISSIONS_SUBPROCESS_TIMEOUT','process_timeout':True,
            'process_limit_seconds':seconds,'last_phase':last}
    except Exception:
        codes={'CONFIGURATION':'PERMISSIONS_CONFIGURATION_REJECTED','SSH':'PERMISSIONS_SSH_REJECTED',
            'TUNNEL':'PERMISSIONS_TUNNEL_REJECTED','SUBPROCESS':'PERMISSIONS_SUBPROCESS_REJECTED',
            'STDERR':'PERMISSIONS_STDERR_REJECTED','RESULT':'PERMISSIONS_RESULT_REJECTED',
            'CLIENT_PROBE':'PERMISSIONS_CLIENT_PROBE_REJECTED'}
        return {'status':codes.get(stage,'PERMISSIONS_UNEXPECTED_REJECTED')}

if __name__=='__main__':
    import paramiko
    report=execute(os.environ,paramiko)
    print(json.dumps(report))
    sys.exit(0 if report.get('status')=='BACKUP_PERMISSIONS_INSPECTED' else 1)
