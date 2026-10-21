"""Fileless upload helper; prepended with the existing directory-check library."""
import base64
import ctypes
import hashlib
import re
from pathlib import PurePosixPath

ROOT = BASE+"/private/mosa2-collector"
ONCE = "upload-20261021-a15aee"
TOKEN = "MOSA2-PRIVATE-UPLOAD-20261021-A15AEE:"
PRIVATE_INODES = (97002064,97002065,97002066,97002067,97002068,97002069)
PAYLOAD_PATHS = ["config/collector-private.example.json","docs/database/migrations/0004_current_observation_provenance.sql","docs/database/seeds/0001_market_units_v1.json","scripts/collector_release/runtime.php","scripts/market_collector/boerse_frankfurt.py","scripts/market_collector/collector.py","scripts/market_collector/contracts.py","scripts/market_collector/frankfurt_request.php","scripts/market_collector/http_transport.py","scripts/market_collector/live_batch.php","scripts/market_collector/live_bridge.py","scripts/market_collector/live_persistence.php","scripts/market_collector/normalizer.py","scripts/market_collector/onboarding.php","scripts/market_collector/runtime_persistence.php","scripts/market_collector/yahoo_chart.py","scripts/phase2/check_expression.php","scripts/phase2/postcheck.php","scripts/phase3b/postcheck.php","scripts/phase3c/market_flow.php","scripts/phase3d/dry_run.php","scripts/phase3k/live_apply.php","scripts/phase3k/unit_schema.php","scripts/phase3l/unit_seed.py","scripts/phase3m/live_seed.php","scripts/phase3m/state_integrity.php","scripts/phase3n/observation_v2.py","scripts/phase3n/unit_catalog_adapter.py","scripts/phase3n/value_adapter.php","scripts/phase3n/writer_plan.py","scripts/phase3o/live_plan.py","scripts/phase3o/live_writer.php","scripts/phase3o/state_integrity.php"]
PUBLIC = tuple(BASE+"/"+p for p in ("httpdocs","mosa.scharwerk.de","mosa2-test.scharwerk.de"))

def guard():
    identity(os)
    for p,ino in zip(TARGETS,PRIVATE_INODES):
        row=inspect(os,p)
        need((row["device"],row["inode"])==(64768,ino),"PRIVATE_ROOT_REPLACED")
    need(all(not inside(ROOT,p) and not inside(p,ROOT) for p in PUBLIC),"PUBLIC_ROOT_OVERLAP")

def unique(pairs):
    out={}
    for k,v in pairs:
        need(k not in out,"DUPLICATE_JSON_KEY");out[k]=v
    return out

def compact(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(",",":"))+"\n").encode()

def plan(data):
    need(re.fullmatch(r"[0-9a-f]{40}",data.get("commit","")) is not None,"COMMIT")
    commit=data["commit"]
    need(data.get("authorization")==TOKEN+commit,"AUTHORIZATION")
    need(re.fullmatch(r"[1-9][0-9]{0,19}",data.get("run_id","")) is not None,"RUN_ID")
    manifest=data["manifest"]
    need(manifest["format"]=="mosa2-collector-release-v1" and manifest["commit"]==commit,"MANIFEST_COMMIT")
    need(hashlib.sha256(compact(manifest)).hexdigest()==data["manifest_sha256"],"MANIFEST_DIGEST")
    rows=manifest["files"]
    need([r["path"] for r in rows]==PAYLOAD_PATHS and len(rows)==33,"EXACT_FILE_SET")
    need(manifest["payload_bytes"]==sum(r["size"] for r in rows)==248105,"PAYLOAD_SIZE")
    for row in rows:
        p=PurePosixPath(row["path"])
        need(not p.is_absolute() and str(p)==row["path"] and ".." not in p.parts
             and "\\" not in row["path"] and row["mode"]=="0600"
             and type(row["size"]) is int and 0<=row["size"]<=32768
             and re.fullmatch(r"[0-9a-f]{64}",row["sha256"]) is not None,"FILE_CONTRACT")
    dirs=sorted({str(parent) for row in rows for parent in PurePosixPath(row["path"]).parents
                 if str(parent)!="."},key=lambda p:(p.count("/"),p))
    return commit,commit+"-"+data["run_id"],rows,dirs

def folder(path):
    need(path.startswith(ROOT+"/") and not any(x in (".","..") for x in path.split("/")),
         "FOLDER_SCOPE")
    fd=checked_fd(os,ROOT)
    current=ROOT
    try:
        for part in path[len(ROOT)+1:].split("/"):
            s=os.stat(part,dir_fd=fd,follow_symlinks=False)
            need(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode)
                 and (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(UID,GID,0o700),"PRIVATE_DIRECTORY")
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            try:
                f=os.fstat(child)
                need((f.st_dev,f.st_ino)==(s.st_dev,s.st_ino),"DIRECTORY_RACE")
            except BaseException:
                os.close(child);raise
            os.close(fd);fd=child;current+="/"+part
        need(os.path.realpath(path)==path,"CANONICAL_FOLDER")
        return fd
    except BaseException:
        os.close(fd);raise

def missing(fd,name):
    try:os.stat(name,dir_fd=fd,follow_symlinks=False)
    except FileNotFoundError:return
    raise Stop("DESTINATION_COLLISION")

def make(parent,name):
    guard()
    fd=folder(parent)
    try:
        os.mkdir(name,0o700,dir_fd=fd)
    finally:os.close(fd)
    fd=folder(parent+"/"+name)
    try:return os.fstat(fd).st_ino
    finally:os.close(fd)

def capability():
    # Linux x86_64 renameat2 syscall ABI: arch/x86/entry/syscalls/syscall_64.tbl, number 316.
    # Reject other ABIs instead of risking a different syscall number.
    import errno
    need(sys.platform=="linux" and os.uname().machine=="x86_64"
         and ctypes.sizeof(ctypes.c_void_p)==8 and ctypes.sizeof(ctypes.c_long)==8,
         "ATOMIC_NOREPLACE_ABI_UNSUPPORTED")
    libc=ctypes.CDLL(None,use_errno=True)
    need(hasattr(libc,"syscall"),"ATOMIC_NOREPLACE_UNAVAILABLE")
    syscall=libc.syscall
    syscall.argtypes=[ctypes.c_long]
    syscall.restype=ctypes.c_long
    def rename(src,name,dst,target,flags):
        need(flags==1,"RENAME_NOREPLACE_REQUIRED")
        ctypes.set_errno(0)
        return syscall(ctypes.c_long(316),ctypes.c_int(src),ctypes.c_char_p(name),
                       ctypes.c_int(dst),ctypes.c_char_p(target),ctypes.c_uint(1))
    # Empty source names cannot designate any filesystem object. Only ENOENT
    # proves syscall recognition; ENOSYS/EINVAL/EPERM and all other results stop.
    # No file or directory is created, renamed or removed by this probe.
    result=rename(-100,b"",-100,b"",1)
    need(result==-1 and ctypes.get_errno()==errno.ENOENT,
         "ATOMIC_NOREPLACE_KERNEL_UNAVAILABLE")
    return rename

def audit(path,rows,dirs):
    """Bounded full set and hash check, only inside this owned release tree."""
    expected_files={r["path"]:r for r in rows}
    expected_dirs=set(dirs)
    actual_files=set();actual_dirs=set()
    pending=[""]
    while pending:
        rel=pending.pop()
        fd=folder(path+("/"+rel if rel else ""))
        try:
            children={p.split("/")[len(rel.split("/")) if rel else 0] for p in
                      set(expected_files)|expected_dirs
                      if (not rel or p.startswith(rel+"/"))}
            seen=set()
            with os.scandir(fd) as entries:
                for item in entries:
                    need(item.name in children and item.name not in seen,"UNKNOWN_REMOTE_ENTRY")
                    seen.add(item.name)
                    name=(rel+"/" if rel else "")+item.name
                    s=item.stat(follow_symlinks=False)
                    need(not stat.S_ISLNK(s.st_mode),"REMOTE_SYMLINK")
                    if name in expected_dirs:
                        need(stat.S_ISDIR(s.st_mode) and
                             (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(UID,GID,0o700),"REMOTE_DIR_METADATA")
                        actual_dirs.add(name);pending.append(name)
                    else:
                        row=expected_files[name]
                        need(stat.S_ISREG(s.st_mode) and
                             (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode),s.st_size)==
                             (UID,GID,0o600,row["size"]),"REMOTE_FILE_METADATA")
                        f=os.open(item.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
                        try:
                            fs=os.fstat(f)
                            need((fs.st_dev,fs.st_ino)==(s.st_dev,s.st_ino),"REMOTE_FILE_RACE")
                            raw=os.read(f,row["size"]+1)
                            need(len(raw)==row["size"] and
                                 hashlib.sha256(raw).hexdigest()==row["sha256"],"REMOTE_HASH")
                        finally:os.close(f)
                        actual_files.add(name)
            need(seen==children,"MISSING_REMOTE_ENTRY")
        finally:os.close(fd)
    need(actual_files==set(expected_files) and actual_dirs==expected_dirs,"REMOTE_SET")
    return dict(files=len(actual_files),bytes=sum(r["size"] for r in rows),sha256="PASS",
                complete_set="PASS",uid=UID,gid=GID,directories_mode="0700",files_mode="0600")

def upload_operation(data):
    action=data.get("action")
    need(action in ("prepare","inspect","publish"),"UPLOAD_ACTION")
    commit,stage,rows,dirs=plan(data)
    guard()
    staging=ROOT+"/staging/"+stage
    release=ROOT+"/releases/"+commit
    if action=="inspect":
        return dict(ok=True,action=action,root=ROOT)
    if action=="prepare":
        blobs=data["files"]
        need(set(blobs)==set(PAYLOAD_PATHS),"BLOB_SET")
        payload={}
        for row in rows:
            raw=base64.b64decode(blobs[row["path"]],validate=True)
            need(len(raw)==row["size"] and hashlib.sha256(raw).hexdigest()==row["sha256"],"INPUT_HASH")
            payload[row["path"]]=raw
        capability()
        for parent,name in ((ROOT+"/locks",ONCE),(ROOT+"/staging",stage),(ROOT+"/releases",commit)):
            fd=folder(parent)
            try:missing(fd,name)
            finally:os.close(fd)
        os.umask(0o077)
        lock_inode=make(ROOT+"/locks",ONCE)
        stage_inode=make(ROOT+"/staging",stage)
        for rel in dirs:
            parent,name=rel.rsplit("/",1) if "/" in rel else ("",rel)
            make(staging+("/"+parent if parent else ""),name)
        for row in rows:
            parent,name=row["path"].rsplit("/",1)
            guard()
            fd=folder(staging+"/"+parent)
            try:
                f=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
                try:
                    s=os.fstat(f)
                    need(stat.S_ISREG(s.st_mode) and
                         (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(UID,GID,0o600),"NEW_FILE_MODE")
                    guard()
                    need(os.write(f,payload[row["path"]])==row["size"],"SHORT_FILE_WRITE")
                    os.fsync(f)
                finally:os.close(f)
            finally:os.close(fd)
        summary=audit(staging,rows,dirs)
        return dict(ok=True,action=action,staging=staging,release=release,lock_inode=lock_inode,
                    stage_inode=stage_inode,audit=summary)
    # Publication is admitted only after the independent SFTP staging readback.
    need(data.get("independent_staging_readback") is True,"STAGING_READBACK_REQUIRED")
    lock=folder(ROOT+"/locks/"+ONCE)
    try:need(os.fstat(lock).st_ino==data["lock_inode"],"LOCK_CHANGED")
    finally:os.close(lock)
    stage_fd=folder(staging)
    try:need(os.fstat(stage_fd).st_ino==data["stage_inode"],"STAGE_CHANGED")
    finally:os.close(stage_fd)
    summary=audit(staging,rows,dirs)
    rename=capability()
    guard()
    src,dst=folder(ROOT+"/staging"),folder(ROOT+"/releases")
    try:
        missing(dst,commit)
        s=os.stat(stage,dir_fd=src,follow_symlinks=False)
        need(s.st_ino==data["stage_inode"] and stat.S_ISDIR(s.st_mode),"STAGE_REPLACED")
        if rename(src,stage.encode(),dst,commit.encode(),1)!=0:
            raise OSError(ctypes.get_errno(),"atomic publication failed")
        os.fsync(src);os.fsync(dst)
    finally:
        os.close(src);os.close(dst)
    return dict(ok=True,action=action,release=release,audit=summary,atomic_noreplace=True)

if __name__=="__main__":
    result=dict(ok=False,collector_started=False,database_connections=0,provider_requests=0)
    try:
        request=json.loads(sys.stdin.read(),object_pairs_hook=unique)
        result.update(upload_operation(request))
    except Stop as e:
        result["failure"]=str(e)
    except OSError as e:
        result["failure"]="OS_ERROR";result["errno"]=e.errno
    except Exception as e:
        result["failure_type"]=type(e).__name__
    print(json.dumps(result,sort_keys=True))
