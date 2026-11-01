"""Read the one authorized immutable archive through the existing pinned SSH path."""
import base64
from datetime import datetime
import hashlib
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
    measured=checked(data)
    locks=checked_fd(os,ROOT+'/locks',base_identity=tuple(measured[BASE]))
    runs=checked_fd(os,ROOT+'/runs',base_identity=tuple(measured[BASE]))
    try:
        token=json.dumps({'execution':data['execution'],'commit':data['commit']},sort_keys=True).encode()
        need(read_file(locks,data['execution']+'.consumed')==token,'ORIGINAL_MARKER')
        fd=os.open(data['execution'],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=runs)
        try:
            s=os.fstat(fd)
            need((s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(UID,GID,0o700),'ARCHIVE_DIRECTORY')
            raw=read_file(fd,'response.body');meta_raw=read_file(fd,'response.json')
            metadata=json.loads(meta_raw)
            need(hashlib.sha256(raw).hexdigest()==data['sha256']==metadata['sha256'],'ORIGINAL_HASH')
            need(len(raw)==metadata['bytes'] and len(raw)>0,'ORIGINAL_SIZE')
            need(metadata['execution']==data['execution'] and metadata['commit']==data['commit'],'ORIGINAL_COMMIT')
            need(metadata['url']==data['url'],'ORIGINAL_URL')
            need(read_file(fd,'response.body')==raw and read_file(fd,'response.json')==meta_raw,'STABLE_ARCHIVE')
            return dict(payload=base64.b64encode(raw).decode('ascii'),metadata=metadata,
                archive=dict(identity=measured,sha256=metadata['sha256'],bytes=len(raw),
                    storage_key=ROOT+'/runs/'+data['execution']+'/response.body',durable=True))
        finally:os.close(fd)
    finally:os.close(locks);os.close(runs)

if __name__=='__main__':
    try:print(json.dumps(dict(ok=True,result=read_existing(json.loads(sys.stdin.read())))))
    except Exception:
        print(json.dumps(dict(ok=False,code='ARCHIVE_VALIDATION_FAILED')))
        sys.exit(1)
'''

def load(transport):
    library=directories.REMOTE_SOURCE.split('\nif __name__=="__main__":')[0]
    archive=(ROOT/'scripts/fundamentals/archive_remote.py').read_text(encoding='utf-8').split("\nif __name__ == '__main__':")[0]
    source=library+'\n'+archive+'\n'+READ_SOURCE
    request=dict(execution=EXECUTION,commit=COMMIT,sha256=SHA256,url=zeiss.URL)
    code,out,err,_=remote.remote_call(transport,shlex.join([directories.PYTHON,'-I','-B','-c',source]),json.dumps(request).encode(),timeout=60)
    if code or err:raise ValueError('ARCHIVE_VALIDATION_FAILED')
    reply=json.loads(out)
    if reply.get('ok') is not True:raise ValueError('ARCHIVE_VALIDATION_FAILED')
    result=reply['result'];raw=base64.b64decode(result.pop('payload'),validate=True);m=result['metadata']
    if hashlib.sha256(raw).hexdigest()!=SHA256 or len(raw)!=m['bytes']:raise ValueError('ARCHIVE_VALIDATION_FAILED')
    if m['url']!=zeiss.URL or m['commit']!=COMMIT or m['execution']!=EXECUTION:raise ValueError('ARCHIVE_VALIDATION_FAILED')
    times=[datetime.strptime(m[k],'%Y-%m-%d %H:%M:%S.%f') for k in ('request_started_at','observed_at')]
    if times[0]>times[1] or times[1].strftime('%Y-%m-%d')!='2026-11-01':raise ValueError('ARCHIVE_TIME_INVALID')
    if type(m['http_status']) is not int or not 100<=m['http_status']<=599 or not isinstance(m['content_type'],str):raise ValueError('ARCHIVE_HTTP_METADATA_INVALID')
    return raw,result
