"""Definitions appended to the existing no-follow Dogado directory library."""
import re
import time

QUEUE = BASE + '/private/mosa2-collector/history'
TARGETS += (QUEUE,)


def queue_operation(data):
    need((os.getuid(), os.geteuid(), os.getgid(), os.getegid()) == (UID, UID, GID, GID), 'ACCOUNT')
    action = data['action']
    need(action in ('setup', 'claim', 'finish'), 'ACTION')
    os.umask(0o077)
    if action == 'setup':
        parent = checked_fd(os, QUEUE.rsplit('/', 1)[0])
        try:
            try:
                os.mkdir('history', 0o700, dir_fd=parent)
                os.fsync(parent)
            except FileExistsError:
                pass
        finally:
            os.close(parent)

    fd = checked_fd(os, QUEUE)
    try:
        def read(name):
            handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            with os.fdopen(handle, 'rb') as stream:
                info = os.fstat(stream.fileno())
                need(stat.S_ISREG(info.st_mode) and
                     (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode), info.st_nlink) == (UID, GID, 0o600, 1)
                     and info.st_size <= 4096, 'QUEUE_FILE')
                return json.loads(stream.read(4097))

        def write(name, value):
            raw = json.dumps(value, separators=(',', ':')).encode()
            temporary = '.write-' + os.urandom(16).hex()
            handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            try:
                with os.fdopen(handle, 'wb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            finally:
                os.unlink(temporary, dir_fd=fd)
            os.fsync(fd)

        if action == 'setup':
            try:
                write('.queue-lock', {})
            except FileExistsError:
                read('.queue-lock')
            return {'ready': True}
        job_id = data['id']
        need(re.fullmatch('[0-9a-f]{64}', job_id or '') is not None or
             (action == 'claim' and job_id is None), 'REQUEST_ID')
        run = data['run']
        need(re.fullmatch('[0-9]{1,24}', run) is not None, 'RUN')
        if action == 'finish':
            need(read(job_id + '.claim')['run'] == run, 'JOB_CLAIM')
            result = data['result']
            need(result['status'] in ('complete', 'partial', 'unavailable', 'conflict', 'unknown', 'failed'),
                 'JOB_RESULT')
            write(job_id + '.result', dict(result, run=run))
            return {'saved': True}

        names = set(os.listdir(fd))
        need(len(names) <= 2050, 'QUEUE_BOUND')
        candidates = []
        for name in names:
            if re.fullmatch('[0-9a-f]{64}\\.request', name) is None:
                continue
            candidate = name[:-8]
            if (job_id is None or candidate == job_id) and candidate + '.claim' not in names:
                request = read(name)
                candidates.append((request['at'], candidate, request))
        if not candidates:
            return {'job': None}
        _, chosen, request = min(candidates)
        # A claim is permanent, including in case of cancellation or an unknown commit.
        write(chosen + '.claim', {'at': int(time.time()), 'run': run})
        return {'job': dict(request, id=chosen)}
    finally:
        os.close(fd)


if __name__ == '__main__':
    try:
        print(json.dumps({'ok': True, 'result': queue_operation(json.loads(sys.stdin.read()))}))
    except Exception:
        print('{"ok":false,"code":"HISTORY_QUEUE_STOP"}')
        sys.exit(1)
