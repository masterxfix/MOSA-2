"""One-shot process supervisor. Prepended with the existing private path verifier."""
import fcntl
import hashlib
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import time

RELEASE_COMMIT="92274a79550b8acd719434459022da6de5261d2e"
ROOT=BASE+"/private/mosa2-collector"
RELEASE=ROOT+"/releases/"+RELEASE_COMMIT
ONCE="first-live-PNE-DE000A0JBPG2-"+RELEASE_COMMIT
RUN=ROOT+"/runs/"+ONCE
TOKEN="MOSA2-PNE-FIRST-LIVE-20261021:"
PHP="/opt/plesk/php/8.4/bin/php"
PHP_FLAGS=("-d","display_errors=0","-d","log_errors=0","-d","opcache.enable_cli=0",
           "-d","opcache.file_cache=","-d","memory_limit=128M")
INODES=(97002064,97002065,97002066,97002067,97002068,97002069)

def guard():
    identity(os)
    for path,inode in zip(TARGETS,INODES):
        row=inspect(os,path)
        need((row["device"],row["inode"])==(64768,inode),"PRIVATE_ROOT_REPLACED")

def valid_input(data):
    import re
    commit=data.get("commit","")
    need(re.fullmatch(r"[0-9a-f]{40}",commit) is not None,"COMMIT")
    need(data.get("authorization")==TOKEN+commit and data.get("isin")=="DE000A0JBPG2","EXACT_ONE_SHOT_AUTHORIZATION")
    need(data.get("release_commit")==RELEASE_COMMIT and data["manifest"]["commit"]==RELEASE_COMMIT,"RELEASE_BINDING")
    need(isinstance(data.get("password"),str) and bool(data["password"]),"DB_SECRET_REQUIRED")
    need(hashlib.sha256(data["php_source"].encode()).hexdigest()==data["php_sha256"],"PHP_SOURCE_BINDING")

def new_metadata(s,mode,directory=False):
    need((stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode))
         and (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(10317,1003,mode),"NEW_OBJECT_METADATA")

def file_once(fd,name,raw):
    guard()
    f=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
    try:
        new_metadata(os.fstat(f),0o600)
        need(os.write(f,raw)==len(raw),"SHORT_WRITE");os.fsync(f)
    finally:os.close(f)

def stop_group(p):
    try:os.killpg(p.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:p.wait(timeout=1)
    except subprocess.TimeoutExpired:pass
    try:os.killpg(p.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    p.wait(timeout=3)

SAFE_FAILURE_CODES=frozenset((
    "COMMIT","EXACT_ONE_SHOT_AUTHORIZATION","RELEASE_BINDING","DB_SECRET_REQUIRED",
    "PHP_SOURCE_BINDING","PRIVATE_ROOT_REPLACED","NEW_OBJECT_METADATA","SHORT_WRITE","RUN_PATH",
    "COLLECTOR_DEADLINE","COLLECTOR_OUTPUT_LIMIT","SECRET_INPUT_LIMIT","RESULT_STATUS",
    "PHP_SPAWN_FAILED","PHP_ADDRESS_SPACE_EXHAUSTED","PHP_SYNTAX_ERROR","PHP_START_PERMISSION",
    "PHP_NONZERO_EXIT","PHP_STDERR","PHP_RESULT_INVALID","PHP_IO_FAILED",
    "RUN_ALREADY_EXISTS","SUPERVISOR_CHECK_FAILED","INPUT_LIMIT","SECRET_OUTPUT_BLOCKED",
    "PROCESS_UID_GID_MISMATCH","ACCOUNT_CWD_CHANGED","WEBROOT_OVERLAP",
    "PATH_TYPE_OR_SYMLINK","PATH_CHANGED","BASE_OWNER_OR_MODE_CHANGED",
    "BASE_IDENTITY_CHANGED","PRIVATE_OWNER_OR_MODE","SYSTEM_ANCESTOR_CHANGED",
    "CANONICAL_PATH_MISMATCH","DIRECTORY_POSTCHECK","UNAPPROVED_PATH"))

def safe_code(error):
    value=str(error)
    return value if isinstance(error,Stop) and value in SAFE_FAILURE_CODES else "SUPERVISOR_CHECK_FAILED"

def process_code(code,stderr):
    # Classification only. Never return any captured output or exception message.
    e=bytes(stderr).lower()
    if any(x in e for x in (b"failed to map segment",b"cannot allocate memory",b"out of memory",b"mmap")):
        return "PHP_ADDRESS_SPACE_EXHAUSTED"
    if b"parse error" in e or b"syntax error" in e:return "PHP_SYNTAX_ERROR"
    if b"permission denied" in e:return "PHP_START_PERMISSION"
    return "PHP_STDERR" if e else ("PHP_NONZERO_EXIT" if code else "PHP_RESULT_INVALID")

class ChildStop(Stop):
    def __init__(self,code,phase,started,exitcode):
        super().__init__(code if code in SAFE_FAILURE_CODES else "SUPERVISOR_CHECK_FAILED")
        self.details=dict(failure_code=safe_code(self),failure_phase=phase,
                          php_process_started=started,php_exitcode=exitcode)

def child(source,password):
    try:
        p=subprocess.Popen([PHP,*PHP_FLAGS,"-r",source],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=RELEASE,start_new_session=True,
            env=dict(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin",PYTHONDONTWRITEBYTECODE="1"))
    except Exception:
        raise ChildStop("PHP_SPAWN_FAILED","php_spawn",False,None) from None
    selector=selectors.DefaultSelector();out=bytearray();err=bytearray();phase="php_input"
    try:
        wire=json.dumps(dict(isin="DE000A0JBPG2",password=password),separators=(",",":")).encode()
        need(len(wire)<=8192,"SECRET_INPUT_LIMIT")
        p.stdin.write(wire);p.stdin.close()
        phase="php_io"
        for stream,buffer in ((p.stdout,out),(p.stderr,err)):
            os.set_blocking(stream.fileno(),False)
            selector.register(stream,selectors.EVENT_READ,buffer)
        end=time.monotonic()+120
        while selector.get_map():
            need(time.monotonic()<end,"COLLECTOR_DEADLINE")
            for key,unused in selector.select(timeout=0.1):
                raw=os.read(key.fileobj.fileno(),4096)
                if raw:key.data.extend(raw)
                else:selector.unregister(key.fileobj)
                need(len(out)+len(err)<=65536,"COLLECTOR_OUTPUT_LIMIT")
        code=p.wait(timeout=3);phase="php_exit"
        if code or err:raise ChildStop(process_code(code,err),phase,True,code)
        phase="php_result"
        try:result=json.loads(out)
        except (ValueError,TypeError):raise ChildStop("PHP_RESULT_INVALID",phase,True,code) from None
        if not isinstance(result,dict):raise ChildStop("PHP_RESULT_INVALID",phase,True,code)
        result.update(php_process_started=True,php_exitcode=code)
        return result
    except ChildStop:raise
    except Exception as error:
        raise ChildStop(safe_code(error) if isinstance(error,Stop) else "PHP_IO_FAILED",
                        phase,True,p.poll()) from None
    finally:
        stop_group(p);selector.close()
        for stream in (p.stdin,p.stdout,p.stderr):
            if not stream.closed:stream.close()

def run_once(data):
    valid_input(data);guard();integrity(Path(RELEASE),data["manifest"])
    os.umask(0o077)
    runs=checked_fd(os,ROOT+"/runs")
    fd=None;lock=None;begun=False
    report=dict(ok=False,status="FAILED",stage="private_preflight",isin="DE000A0JBPG2",
                asset="PNE AG",commit=data["commit"],release_commit=RELEASE_COMMIT,
                release=RELEASE,run=RUN,provider_requests=0,provider_started=False,
                php_process_started=False,php_exitcode=None,commit_state="nicht bestätigt")
    try:
        guard()
        # Deterministic across source commits. Never reuse, overwrite or clean up.
        try:os.mkdir(ONCE,0o700,dir_fd=runs)
        except FileExistsError:raise Stop("RUN_ALREADY_EXISTS") from None
        s=os.stat(ONCE,dir_fd=runs,follow_symlinks=False);new_metadata(s,0o700,True)
        fd=os.open(ONCE,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=runs)
        need(os.fstat(fd).st_ino==s.st_ino and os.path.realpath(RUN)==RUN,"RUN_PATH")
        lock=os.open("job.lock",os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=fd)
        new_metadata(os.fstat(lock),0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        file_once(fd,"started.json",json.dumps(dict(commit=data["commit"],release=RELEASE_COMMIT,
            isin="DE000A0JBPG2",php_sha256=data["php_sha256"],automatic_retry=False)).encode())
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(45,45))
        # Normal PHP 8.4 extensions exhaust 256 MiB of VIRTUAL address space (exit 254).
        # 1 GiB was proven by the fileless no-DB startup comparison; PHP heap stays 128 MiB.
        resource.setrlimit(resource.RLIMIT_AS,(1024*1024*1024,1024*1024*1024))
        os.environ.clear();os.environ.update(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin",PYTHONDONTWRITEBYTECODE="1")
        begun=True;report["stage"]="collector";report["commit_state"]="unbekannt";report["php_process_started"]="UNBESTAETIGT"
        result=child(data["php_source"],data["password"])
        need(result.get("status") in ("COMPLETE","FAILED","OUTCOME_UNKNOWN"),"RESULT_STATUS")
        report.update(result)
        committed=result.get("result",{}).get("committed")
        report["commit_state"]="bestätigt" if committed is True else ("nicht bestätigt" if committed is False else "unbekannt")
        guard();integrity(Path(RELEASE),data["manifest"]);report["release_unchanged"]="PASS"
    except Exception as error:
        report.update(ok=False,failure_type="ChildStop" if isinstance(error,ChildStop) else "Stop",
                      failure_code=safe_code(error),failure_phase=report["stage"])
        if isinstance(error,ChildStop):report.update(error.details)
        if begun:report["status"]="OUTCOME_UNKNOWN"
        if report["php_process_started"] is False:report["commit_state"]="nicht bestätigt"
    finally:
        if fd is not None:
            try:
                marker=os.stat("provider-consumed.lock",dir_fd=fd,follow_symlinks=False)
                new_metadata(marker,0o600);report["provider_requests"]=1;report["provider_marker_retained"]=True;report["provider_started"]=True
            except FileNotFoundError:report["provider_requests"]=0;report["provider_started"]=False
            except Exception:report.update(ok=False,status="OUTCOME_UNKNOWN",marker_check="FAIL",provider_started="UNBESTAETIGT")
            text=json.dumps(report,sort_keys=True)
            password=data["password"]
            if password in text or json.dumps(password)[1:-1] in text:
                report=dict(ok=False,status="OUTCOME_UNKNOWN",failure="SECRET_OUTPUT_BLOCKED")
                text=json.dumps(report)
            try:file_once(fd,"result.json",text.encode())
            except Exception:
                report.update(ok=False,receipt_persistence="FAIL")
                if begun:report["status"]="OUTCOME_UNKNOWN"
        if lock is not None:os.close(lock)
        if fd is not None:os.close(fd)
        os.close(runs)
    return report

if __name__=="__main__":
    try:
        wire=sys.stdin.read(100001);need(len(wire)<=100000,"INPUT_LIMIT")
        data=json.loads(wire);report=run_once(data)
    except Exception as error:
        report=dict(ok=False,status="FAILED",stage="supervisor_preflight",failure_code=safe_code(error),failure_phase="supervisor_preflight",
                    php_process_started=False,php_exitcode=None,provider_started=False,commit_state="nicht bestätigt",provider_requests=0)
    print(json.dumps(report,sort_keys=True))
