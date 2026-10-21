"""Generic batch supervision using the existing guarded process and file functions."""
LIVE_ENABLED=False  # Requires a later separately reviewed activation commit and user authorization.
BATCH_TOKEN="MOSA2-DOGADO-BATCH:"
SAFE_FAILURE_CODES=SAFE_FAILURE_CODES|frozenset((
    "BATCH_LIVE_NOT_AUTHORIZED","BATCH_INPUT","BATCH_SELECTION","BATCH_RUN_ID",
    "BATCH_LOCK_BUSY","BATCH_LOCK_METADATA","BATCH_MARKER_MISMATCH","BATCH_RESULT"))

def validate_batch(data):
    import re
    need(LIVE_ENABLED,"BATCH_LIVE_NOT_AUTHORIZED")
    commit=data.get("commit","");label=data.get("run_id","");selection=data.get("selection")
    need(re.fullmatch(r"[0-9a-f]{40}",commit) is not None,"COMMIT")
    need(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}",label) is not None,"BATCH_RUN_ID")
    need(isinstance(selection,list) and 1<=len(selection)<=10
         and all(isinstance(v,str) and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]",v) for v in selection)
         and len(set(selection))==len(selection),"BATCH_SELECTION")
    digest=hashlib.sha256(json.dumps(selection,separators=(",",":")).encode()).hexdigest()
    need(data.get("authorization")==BATCH_TOKEN+commit+":"+label+":"+digest,"EXACT_ONE_SHOT_AUTHORIZATION")
    need(data.get("release_commit")==RELEASE_COMMIT and data["manifest"]["commit"]==RELEASE_COMMIT,"RELEASE_BINDING")
    need(isinstance(data.get("password"),str) and bool(data["password"]),"DB_SECRET_REQUIRED")
    need(hashlib.sha256(data["php_source"].encode()).hexdigest()==data["php_sha256"],"PHP_SOURCE_BINDING")
    return "batch-"+commit+"-"+label+"-"+digest[:16]

def provider_markers(fd,count):
    found=0
    for i in range(count):
        name="asset-"+format(i+1,"02d")
        try:s=os.stat(name,dir_fd=fd,follow_symlinks=False)
        except FileNotFoundError:continue
        new_metadata(s,0o700,True)
        childfd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            need(os.fstat(childfd).st_ino==s.st_ino,"RUN_PATH")
            try:marker=os.stat("provider-consumed.lock",dir_fd=childfd,follow_symlinks=False)
            except FileNotFoundError:continue
            new_metadata(marker,0o600);found+=1
        finally:os.close(childfd)
    return found

def run_batch_once(data):
    global RUN
    name=validate_batch(data);RUN=ROOT+"/runs/"+name
    guard();integrity(Path(RELEASE),data["manifest"])
    os.umask(0o077)
    runs=checked_fd(os,ROOT+"/runs");locks=checked_fd(os,ROOT+"/locks")
    fd=None;lock=None;begun=False
    r=dict(ok=False,overall_status="FAILED_BEFORE_FIRST_COMMIT",requested_count=len(data["selection"]),
           started_count=0,completed_count=0,provider_requests=0,stage="private_preflight",
           run=RUN,commit=data["commit"],release_commit=RELEASE_COMMIT,automatic_retries=0,
           integrity_before="PASS",integrity_after="NOT_CHECKED")
    try:
        guard()
        lock=os.open("collector-batch.lock",os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600,dir_fd=locks)
        new_metadata(os.fstat(lock),0o600)
        need(os.fstat(lock).st_size==0,"BATCH_LOCK_METADATA")
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Stop("BATCH_LOCK_BUSY") from None
        try:os.mkdir(name,0o700,dir_fd=runs)
        except FileExistsError:raise Stop("RUN_ALREADY_EXISTS") from None
        s=os.stat(name,dir_fd=runs,follow_symlinks=False);new_metadata(s,0o700,True)
        fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=runs)
        need(os.fstat(fd).st_ino==s.st_ino and os.path.realpath(RUN)==RUN,"RUN_PATH")
        file_once(fd,"started.json",json.dumps(dict(commit=data["commit"],release=RELEASE_COMMIT,
            selection=data["selection"],php_sha256=data["php_sha256"],automatic_retry=False)).encode())
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(45*len(data["selection"]),45*len(data["selection"])))
        resource.setrlimit(resource.RLIMIT_AS,(1024*1024*1024,1024*1024*1024))
        os.environ.clear();os.environ.update(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin",PYTHONDONTWRITEBYTECODE="1")
        begun=True;r["stage"]="batch"
        result=child(data["php_source"],data["password"],dict(selection=data["selection"]),deadline=120*len(data["selection"]))
        need(result.get("overall_status") in ("COMPLETE","PARTIAL_FAILED","FAILED_BEFORE_FIRST_COMMIT","OUTCOME_UNKNOWN"),"BATCH_RESULT")
        r.update(result)
    except Exception as e:
        r.update(ok=False,failure_code=safe_code(e),failure_phase=r["stage"])
        if isinstance(e,ChildStop):r.update(e.details)
        if begun:r["overall_status"]="OUTCOME_UNKNOWN"
    finally:
        try:
            if fd is not None:
                count=provider_markers(fd,len(data["selection"]))
                if r.get("provider_requests") is not None and r["provider_requests"]!=count and r.get("overall_status")=="COMPLETE":
                    raise Stop("BATCH_MARKER_MISMATCH")
                r["provider_requests"]=count;r["provider_markers_retained"]=True
            guard();integrity(Path(RELEASE),data["manifest"]);r["integrity_after"]="PASS"
        except Exception as e:
            r.update(ok=False,integrity_after="FAIL",failure_code=safe_code(e),provider_requests=None)
            if begun:r["overall_status"]="OUTCOME_UNKNOWN"
        if fd is not None:
            text=json.dumps(r,sort_keys=True);password=data["password"]
            if password in text or json.dumps(password)[1:-1] in text:
                r=dict(ok=False,overall_status="OUTCOME_UNKNOWN",failure_code="SECRET_OUTPUT_BLOCKED");text=json.dumps(r)
            try:file_once(fd,"result.json",text.encode())
            except Exception:
                r.update(ok=False,receipt_persistence="FAIL")
                if begun:r["overall_status"]="OUTCOME_UNKNOWN"
        if lock is not None:os.close(lock)
        if fd is not None:os.close(fd)
        os.close(locks);os.close(runs)
    return r

if __name__=="__main__":
    try:
        raw=sys.stdin.read(200001);need(len(raw)<=200000,"INPUT_LIMIT")
        r=run_batch_once(json.loads(raw))
    except Exception as e:
        r=dict(ok=False,overall_status="FAILED_BEFORE_FIRST_COMMIT",failure_code=safe_code(e),provider_requests=0)
    print(json.dumps(r,sort_keys=True))
