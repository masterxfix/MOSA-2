"""One explicitly authorized six-directory operation; no upload or collector capability."""
import json
import logging
import os
import shlex
import sys

import collector_actions as shared
import collector_db_locality as remote
import deploy_test_sftp as profile

AUTHORIZATION = "MOSA2-CREATE-SIX-DIRS-2026-10-21"
PYTHON = "/opt/alt/python311/bin/python3.11"
REMOTE_SOURCE = r'''
import json
import os
import stat
import sys

BASE = "/var/www/vhosts/web213.server10.configcenter.info"
NAMES = ("private", "private/mosa2-collector",
         "private/mosa2-collector/releases", "private/mosa2-collector/staging",
         "private/mosa2-collector/runs", "private/mosa2-collector/locks")
TARGETS = tuple(BASE+"/"+n for n in NAMES)
# The three top-level trees encompass all eight Plesk mappings read on 21 October.
WEBROOTS = tuple(BASE+"/"+n for n in ("httpdocs","mosa.scharwerk.de","mosa2-test.scharwerk.de"))
AUTHORIZATION = "MOSA2-CREATE-SIX-DIRS-2026-10-21"
BASE_ID = (64768, 5248112)
UID, GID = 10317, 1003

class Stop(RuntimeError):
    pass

def need(ok, reason):
    if not ok:
        raise Stop(reason)

def inside(a, b):
    return a == b or a.startswith(b+"/")

def metadata(path, s):
    return dict(path=path, directory=stat.S_ISDIR(s.st_mode), symlink=stat.S_ISLNK(s.st_mode),
                uid=s.st_uid, gid=s.st_gid, mode=format(stat.S_IMODE(s.st_mode),"04o"),
                device=s.st_dev, inode=s.st_ino)

def checked_fd(api, path):
    """Walk fixed names with no-follow dirfds; never list a directory."""
    need(path == BASE or path in TARGETS, "UNAPPROVED_PATH")
    fd = api.open("/", api.O_RDONLY|api.O_DIRECTORY|api.O_NOFOLLOW)
    current = ""
    try:
        for part in path.split("/")[1:]:
            current += "/"+part
            before = api.stat(part,dir_fd=fd,follow_symlinks=False)
            need(stat.S_ISDIR(before.st_mode) and not stat.S_ISLNK(before.st_mode), "PATH_TYPE_OR_SYMLINK")
            child = api.open(part,api.O_RDONLY|api.O_DIRECTORY|api.O_NOFOLLOW,dir_fd=fd)
            try:
                after = api.fstat(child)
                need((after.st_dev,after.st_ino) == (before.st_dev,before.st_ino), "PATH_CHANGED")
            except BaseException:
                api.close(child)
                raise
            api.close(fd);fd=child
            if current == BASE:
                need((after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode)) == (UID,1002,0o710),
                     "BASE_OWNER_OR_MODE_CHANGED")
                need((after.st_dev,after.st_ino) == BASE_ID, "BASE_IDENTITY_CHANGED")
            elif inside(current,BASE+"/private"):
                need((after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode)) == (UID,GID,0o700),
                     "PRIVATE_OWNER_OR_MODE")
            else:
                need((after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode)) == (0,0,0o755),
                     "SYSTEM_ANCESTOR_CHANGED")
        need(api.path.realpath(path) == path, "CANONICAL_PATH_MISMATCH")
        return fd
    except BaseException:
        api.close(fd)
        raise

def identity(api):
    need((api.getuid(),api.geteuid(),api.getgid(),api.getegid()) == (UID,UID,GID,GID),
         "PROCESS_UID_GID_MISMATCH")
    need(api.getcwd() == BASE, "ACCOUNT_CWD_CHANGED")
    need(len(TARGETS) == 6 and len(set(TARGETS)) == 6, "DIRECTORY_CONTRACT")
    for p in TARGETS:
        need(inside(p,BASE+"/private") and all(not inside(p,w) and not inside(w,p) for w in WEBROOTS),
             "WEBROOT_OVERLAP")
    fd = checked_fd(api,BASE)
    api.close(fd)

def absent(api):
    # All targets must be absent before the first write. Descendants of missing
    # parents are necessarily absent; no traversal through missing objects.
    fd=checked_fd(api,BASE)
    try:
        try:
            api.stat("private",dir_fd=fd,follow_symlinks=False)
        except FileNotFoundError:
            return
        raise Stop("UNEXPECTED_EXISTING_TARGET")
    finally:
        api.close(fd)

def stable_parent(api, path, fd):
    # Reopen the complete anchored chain immediately before each mkdir.
    fresh = checked_fd(api,path)
    try:
        a,b = api.fstat(fd),api.fstat(fresh)
        need((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino), "PARENT_REPLACED")
    finally:
        api.close(fresh)

def inspect(api,path):
    fd = checked_fd(api,path)
    try:
        row = metadata(path,api.fstat(fd))
        need(row["directory"] and not row["symlink"] and row["uid"]==UID
             and row["gid"]==GID and row["mode"]=="0700","DIRECTORY_POSTCHECK")
        return row
    finally:
        api.close(fd)

def run(action, authorization, api=os):
    r = dict(ok=False, action=action, attempted=[], created=[], verified=[],
             file_writes=0, provider_requests=0, database_connections=0,
             deployment_enabled=False, plan_budget_bytes=67108864)
    try:
        need(action in ("create","readback"),"ACTION")
        need(authorization==AUTHORIZATION,"EXPLICIT_AUTHORIZATION_REQUIRED")
        identity(api)
        if action=="create":
            absent(api)
            api.umask(0o077)
            for path in TARGETS:
                parent,name=path.rsplit("/",1)
                fd=checked_fd(api,parent)
                try:
                    stable_parent(api,parent,fd)
                    # Exclusive mkdir: an object appearing after preflight fails closed.
                    r["attempted"].append(path)
                    api.mkdir(name,0o700,dir_fd=fd)
                    r["created"].append(path)
                    # Record actual metadata even when the immediate invariant fails.
                    s=api.stat(name,dir_fd=fd,follow_symlinks=False)
                    row=metadata(path,s)
                    r["last_created_metadata"]=row
                    need(row["directory"] and not row["symlink"] and
                         (row["uid"],row["gid"],row["mode"])==(UID,GID,"0700"),
                         "CREATED_OWNER_MODE_OR_TYPE_MISMATCH")
                    opened=api.open(name,api.O_RDONLY|api.O_DIRECTORY|api.O_NOFOLLOW,dir_fd=fd)
                    try:
                        now=api.fstat(opened)
                        need((now.st_dev,now.st_ino)==(s.st_dev,s.st_ino),"CREATED_OBJECT_REPLACED")
                    finally:
                        api.close(opened)
                    checked=inspect(api,path)
                    need((checked["device"],checked["inode"])==(s.st_dev,s.st_ino),
                         "CREATED_PATH_REPLACED")
                    r["verified"].append(checked)
                finally:
                    api.close(fd)
        else:
            # Fresh interpreter and fresh SSH connection: no creation FDs/cache reused.
            for path in TARGETS:
                r["verified"].append(inspect(api,path))
        r["ok"]=len(r["verified"])==6
    except Stop as e:
        r["failure"]=str(e)
    except OSError as e:
        r["failure"]="OS_ERROR"
        r["errno"]=e.errno
        r["failure_type"]=type(e).__name__
    except Exception as e:
        r["failure"]="PROCESS_ERROR"
        r["failure_type"]=type(e).__name__
    return r

if __name__=="__main__":
    data=json.loads(sys.stdin.read())
    need(set(data)=={"action","authorization"},"INPUT_FIELDS")
    print(json.dumps(run(data["action"],data["authorization"]),sort_keys=True))
'''

def invoke(transport, action):
    data=json.dumps(dict(action=action,authorization=AUTHORIZATION)).encode()
    command=shlex.join([PYTHON,"-I","-B","-c",REMOTE_SOURCE])
    code,out,errors,elapsed=remote.remote_call(transport,command,data,timeout=40)
    if code or errors:
        raise remote.ProbeError("DIRECTORY_COMMAND_FAILED_OUTCOME_REQUIRES_READBACK")
    result=json.loads(out)
    if not isinstance(result,dict) or result.get("action")!=action or type(result.get("ok")) is not bool:
        raise remote.ProbeError("INVALID_DIRECTORY_RECEIPT")
    return result


def sftp_readback(sftp, created):
    # Independent metadata only; absolutely no SFTP write method is used.
    expected=[row["path"] for row in created]
    root="/var/www/vhosts/web213.server10.configcenter.info"
    paths=[root+"/private",root+"/private/mosa2-collector"]+[
        root+"/private/mosa2-collector/"+n for n in ("releases","staging","runs","locks")]
    if expected!=paths:
        raise remote.ProbeError("READBACK_SCOPE_MISMATCH")
    import stat
    rows=[]
    # lstat every ancestor before normalize (which can otherwise follow a link).
    ancestors=("/", "/var","/var/www","/var/www/vhosts",root)
    for path in (*ancestors,*paths):
        s=sftp.lstat(path)
        if not stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode):
            raise remote.ProbeError("SFTP_READBACK_PATH_TYPE")
        if path in paths:
            if (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))!=(10317,1003,0o700):
                raise remote.ProbeError("SFTP_READBACK_OWNER_MODE")
            if sftp.normalize(path)!=path:
                raise remote.ProbeError("SFTP_READBACK_CANONICAL")
            rows.append(dict(path=path,uid=s.st_uid,gid=s.st_gid,mode="0700",
                             directory=True,symlink=False,canonical=path))
    return rows


def execute(env,paramiko=None):
    report=dict(ok=False,stage="authorization",creation=None,readback=None,sftp_readback=None,
                deployment_enabled=False,automatic_retries=0)
    if env.get("MOSA_PRIVATE_DIRECTORY_AUTHORIZATION")!=AUTHORIZATION:
        report["failure"]="MISSING_EXPLICIT_DIRECTORY_AUTHORIZATION"
        return report
    try:
        config=profile.configuration(env)
        if paramiko is None:
            import paramiko
        logging.getLogger("paramiko").disabled=True
    except Exception as error:
        report["failure_type"]=type(error).__name__
        return report
    submitted=False
    try:
        report["stage"]="create"
        status={}
        with shared.ssh_client(config,status,paramiko) as transport:
            report["creation_ssh"]=status
            submitted=True
            report["creation"]=invoke(transport,"create")
    except Exception as error:
        report["creation_outcome"]="UNKNOWN_DO_NOT_RETRY"
        report["failure_type"]=type(error).__name__
    if submitted:
        try:
            report["stage"]="independent_readback"
            status={}
            with shared.ssh_client(config,status,paramiko) as transport:
                report["readback_ssh"]=status
                report["readback"]=invoke(transport,"readback")
                if report["readback"]["ok"]:
                    with paramiko.SFTPClient.from_transport(transport) as sftp:
                        sftp.get_channel().settimeout(8)
                        report["sftp_readback"]=sftp_readback(sftp,report["readback"]["verified"])
        except Exception as error:
            report["readback_failure_type"]=type(error).__name__
    a,b=report["creation"],report["readback"]
    report["ok"]=bool(a and a["ok"] and b and b["ok"] and
                      a["verified"]==b["verified"] and report["sftp_readback"]
                      and len(a["created"])==6)
    report["stage"]="finished"
    return report


def main():
    report=execute(os.environ)
    text=shared.public_text(report,os.environ)
    print(text,flush=True)
    return 0 if report["ok"] and json.loads(text).get("ok") else 1


if __name__=="__main__":
    sys.exit(main())
