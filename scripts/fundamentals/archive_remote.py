"""Fileless archive operation, appended to the existing no-follow directory library."""
import base64
import hashlib
import json
import re

ONCE = 'fundamentals-pne2025-20261101-01'
ROOT = BASE + '/private/mosa2-collector'

def checked(data):
    need(data['execution'] == ONCE and re.fullmatch('[0-9a-f]{40}', data['commit']), 'AUTHORIZATION')
    need((os.getuid(), os.geteuid(), os.getgid(), os.getegid()) == (UID, UID, GID, GID), 'ACCOUNT')
    paths = (BASE, BASE+'/private', ROOT, ROOT+'/runs', ROOT+'/locks')
    measured = {}
    for path in paths:
        fd = checked_fd(os, path, base_identity=tuple(measured[BASE]) if BASE in measured else None)
        try:
            s = os.fstat(fd)
            measured[path] = [s.st_dev, s.st_ino]
        finally:
            os.close(fd)
    if data.get('identity') is not None:
        need(measured == data['identity'], 'PRIVATE_PATH_CHANGED')
    return measured

def create_file(fd, name, raw):
    f = os.open(name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(f, 'wb', closefd=False) as out:
            need(out.write(raw) == len(raw), 'SHORT_WRITE')
            out.flush()
            os.fsync(f)
    finally:
        os.close(f)
    os.fsync(fd)

def read_file(fd, name):
    f = os.open(name, os.O_RDONLY|os.O_NOFOLLOW, dir_fd=fd)
    try:
        s = os.fstat(f)
        need(stat.S_ISREG(s.st_mode) and (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode),s.st_nlink)==(UID,GID,0o600,1), 'FILE_PROTECTION')
        need(s.st_size <= 8*1024*1024, 'FILE_BOUND')
        with os.fdopen(f, 'rb', closefd=False) as stream:
            raw = stream.read(8*1024*1024+1)
        need(len(raw)==s.st_size, 'FILE_SIZE')
        return raw
    finally:
        os.close(f)

def operation(data):
    measured = checked(data)
    os.umask(0o077)
    action = data['action']
    need(action in ('reserve','archive','verify'), 'ACTION')
    locks = checked_fd(os, ROOT+'/locks', base_identity=tuple(measured[BASE]))
    runs = checked_fd(os, ROOT+'/runs', base_identity=tuple(measured[BASE]))
    try:
        token = json.dumps({'execution':ONCE,'commit':data['commit']},sort_keys=True).encode()
        if action == 'reserve':
            create_file(locks, ONCE+'.consumed', token)
            os.mkdir(ONCE, 0o700, dir_fd=runs)
            os.fsync(runs)
            return dict(identity=measured, reserved=True)
        need(read_file(locks, ONCE+'.consumed')==token, 'RESERVATION')
        fd = os.open(ONCE, os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW, dir_fd=runs)
        try:
            s=os.fstat(fd)
            need((s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(UID,GID,0o700), 'ARCHIVE_DIRECTORY')
            metadata = data['metadata']
            need(re.fullmatch('[0-9a-f]{64}',metadata['sha256']) is not None, 'HASH')
            if action == 'archive':
                raw=base64.b64decode(data['payload'],validate=True)
                need(len(raw)==metadata['bytes'] and hashlib.sha256(raw).hexdigest()==metadata['sha256'], 'PAYLOAD_HASH')
                create_file(fd,'response.body',raw)
                create_file(fd,'response.json',json.dumps(metadata,sort_keys=True,ensure_ascii=True).encode())
            raw=read_file(fd,'response.body')
            need(len(raw)==metadata['bytes'] and hashlib.sha256(raw).hexdigest()==metadata['sha256'], 'READBACK_HASH')
            need(json.loads(read_file(fd,'response.json'))==metadata, 'READBACK_METADATA')
            return dict(identity=measured, sha256=metadata['sha256'], bytes=len(raw),
                storage_key=ROOT+'/runs/'+ONCE+'/response.body', mode='0600', durable=True)
        finally:
            os.close(fd)
    finally:
        os.close(locks);os.close(runs)

if __name__ == '__main__':
    try:
        result=operation(json.loads(sys.stdin.read()))
        print(json.dumps(dict(ok=True,result=result)))
    except Exception:
        print(json.dumps(dict(ok=False,code='ARCHIVE_STOP_NO_RETRY')))
        sys.exit(1)
