"""Read the one authorized immutable archive through the existing pinned SSH path."""
import json
from pathlib import Path
import shlex
from scripts import collector_private_directories as directories
from scripts import collector_db_locality as remote
from scripts.fundamentals import zeiss

EXECUTION = 'fundamentals-zeiss2025-20261101-01'
COMMIT = '40f4c10869b1e95f016669805e20ce20e7525afe'
SHA256 = 'a4c91e276485de7bba4cdd1a52c05dd3f506587bba8271b8a453a7ea1f706b4f'
ROOT = Path(__file__).resolve().parents[2]

READ_SOURCE = r'''
def read_existing(data):
    global phase
    phase='ARCHIVE_PATHS'
    measured=checked(data)
    locks=checked_fd(os,ROOT+'/locks',base_identity=tuple(measured[BASE]))
    runs=checked_fd(os,ROOT+'/runs',base_identity=tuple(measured[BASE]))
    try:
        phase='ARCHIVE_MARKER'
        token=json.dumps({'execution':data['execution'],'commit':data['commit']},sort_keys=True).encode()
        need(read_file(locks,data['execution']+'.consumed')==token,'ORIGINAL_MARKER')
        fd=os.open(data['execution'],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=runs)
        try:
            s=os.fstat(fd)
            need((s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(UID,GID,0o700),'ARCHIVE_DIRECTORY')
            phase='ARCHIVE_BYTES'
            raw=read_file(fd,'response.body');meta_raw=read_file(fd,'response.json')
            phase='ARCHIVE_METADATA'
            metadata=json.loads(meta_raw)
            need(hashlib.sha256(raw).hexdigest()==data['sha256']==metadata['sha256'],'ORIGINAL_HASH')
            need(len(raw)==metadata['bytes'] and len(raw)>0,'ORIGINAL_SIZE')
            need(metadata['execution']==data['execution'] and metadata['commit']==data['commit'],'ORIGINAL_COMMIT')
            need(metadata['url']==data['url'],'ORIGINAL_URL')
            times=[datetime.strptime(metadata[k],'%Y-%m-%d %H:%M:%S.%f') for k in ('request_started_at','observed_at')]
            need(times[0]<=times[1] and times[1].strftime('%Y-%m-%d')=='2026-11-01','ORIGINAL_TIME')
            need(type(metadata['http_status']) is int and 100<=metadata['http_status']<=599 and isinstance(metadata['content_type'],str),'ORIGINAL_HTTP_METADATA')
            phase='ARCHIVE_READBACK'
            need(read_file(fd,'response.body')==raw and read_file(fd,'response.json')==meta_raw,'STABLE_ARCHIVE')
            return raw,metadata
        finally:os.close(fd)
    finally:os.close(locks);os.close(runs)

'''

SAFE_REMOTE_CODES={'ORIGINAL_MARKER','ARCHIVE_DIRECTORY','ORIGINAL_HASH','ORIGINAL_SIZE','ORIGINAL_COMMIT',
    'ORIGINAL_URL','ORIGINAL_TIME','ORIGINAL_HTTP_METADATA','STABLE_ARCHIVE','FILE_PROTECTION','FILE_BOUND',
    'FILE_SIZE','AUTHORIZATION','ACCOUNT','PRIVATE_PATH_CHANGED','RESULT_BOUND'}

def source():
    """Transmit reviewed code only; original bytes never leave the remote process."""
    from scripts.fundamentals_archive_diagnose import diagnose, ERRORS
    import inspect
    library=directories.REMOTE_SOURCE.split('\nif __name__=="__main__":')[0]
    archive=(ROOT/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8').split("\nif __name__ == '__main__':")[0]
    modules={name:(ROOT/('scripts/fundamentals/'+name+'.py')).read_text(encoding='utf-8') for name in ('pne','zeiss')}
    setup="""
from datetime import datetime
import types
for package in ('scripts','scripts.fundamentals'):
    module=types.ModuleType(package);module.__path__=[];sys.modules[package]=module
for name,code in MODULES.items():
    full='scripts.fundamentals.'+name
    module=types.ModuleType(full);module.__package__='scripts.fundamentals';sys.modules[full]=module
    exec(compile(code,'<reviewed-adapter>','exec'),module.__dict__)
zeiss=sys.modules['scripts.fundamentals.zeiss']
"""
    return (library+'\n'+archive+'\n'+READ_SOURCE+'\nMODULES='+repr(modules)+
        '\nERRORS='+repr(ERRORS)+'\nSAFE_CODES='+repr(SAFE_REMOTE_CODES)+'\n'+setup+'\n'+inspect.getsource(diagnose)+REMOTE_MAIN)

REMOTE_MAIN = r'''
def run_diagnosis(data):
    global phase
    phase='INPUT'
    report=dict(ok=False,provider_requests=0,database_access=False,archive_writes=False,archive='FAIL')
    try:
        raw,metadata=read_existing(data)
        report.update(archive='PASS',archive_sha256='PASS',
            legacy_transport_would_exceed_limit=4*((len(raw)+2)//3)+len('{"payload": ""}')>65536)
        phase='ADAPTER'
        result=diagnose(raw,metadata)
        report.update(ok=True,phase=phase,diagnosis=result)
        need(len(json.dumps(report).encode())<=16384,'RESULT_BOUND')
    except Exception as exc:
        reason=str(exc)
        code=reason if reason in SAFE_CODES else ('FILE_NOT_FOUND' if isinstance(exc,FileNotFoundError) else
            'ACCESS_DENIED' if isinstance(exc,PermissionError) else 'INVALID_JSON' if isinstance(exc,json.JSONDecodeError) else
            'INVALID_METADATA' if isinstance(exc,(KeyError,TypeError,ValueError)) else 'REMOTE_OPERATION_FAILED')
        report=dict(ok=False,phase=phase,error=code,archive=report['archive'],provider_requests=0,database_access=False,archive_writes=False)
    return report

if __name__=='__main__':
    result=run_diagnosis(REQUEST)
    print(json.dumps(result))
    sys.exit(0 if result['ok'] else 1)
'''

def load(transport):
    request=dict(execution=EXECUTION,commit=COMMIT,sha256=SHA256,url=zeiss.URL)
    bootstrap="import json,sys; p=json.loads(sys.stdin.read()); REQUEST=p['request']; exec(compile(p['source'],'<archive-diagnosis>','exec'))"
    code,out,err,_=remote.remote_call(transport,shlex.join([directories.PYTHON,'-I','-B','-c',bootstrap]),
        json.dumps(dict(request=request,source=source())).encode(),timeout=60)
    if err:raise ValueError('REMOTE_STDERR')
    if len(out)>16384:raise ValueError('RESULT_BOUND')
    try:reply=json.loads(out)
    except (ValueError,UnicodeError):raise ValueError('REMOTE_INVALID_JSON') from None
    if not isinstance(reply,dict) or 'ok' not in reply or (code!=0 and reply.get('ok')):raise ValueError('REMOTE_RESULT_INVALID')
    return reply
