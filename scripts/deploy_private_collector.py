"""Default-closed, explicitly authorized one-shot private release publication."""
import argparse
import json
from pathlib import PurePosixPath
import re

from scripts import deploy_sftp as shared

PROPOSED_ROOT = "/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector"
DIRECTORIES = ("releases", "staging", "runs", "locks")
RESERVE_BYTES = 64 * 1024 * 1024


def inside(child, parent):
    return child == parent or child.startswith(parent + "/")


def proposal(root, webroots):
    """Pure lexical review only: never proves remote existence, ownership or approval."""
    if (type(root) is not str or not re.fullmatch(r"/[A-Za-z0-9_./-]+", root)
            or str(PurePosixPath(root)) != root
            or any(p in (".", "..") for p in root.split("/")[1:])
            or root.endswith("/")):
        raise ValueError("invalid private proposal")
    for public in (*webroots, shared.ABSOLUTE_ROOT, shared.TEST_ROOT):
        if inside(root, public) or inside(public, root):
            raise ValueError("webroot/ancestor target forbidden")
    if root != PROPOSED_ROOT:
        raise ValueError("unreviewed private proposal")
    return dict(proposed_root=root, authorized=False, remote_verified=False,
                upload_enabled=False, directories={p: "0700" for p in DIRECTORIES},
                file_mode="0600", plan_reserve_bytes=RESERVE_BYTES)


def verify_host_key_material(key_bytes, expected):
    """Reuse the existing pinned-key algorithm; no client/network capability."""
    return shared.verify_fingerprint(key_bytes, expected)



TOKEN = "MOSA2-PRIVATE-UPLOAD-20261021-A15AEE:"
ONCE = "upload-20261021-a15aee"
ARCHIVE_SHA256 = "73e34c8d8e13ce37265ef5dded1ceae162140eee5b17341b23ee7dae3e3a68f7"


def modules():
    import sys
    from pathlib import Path
    directory=Path(__file__).resolve().parent
    if str(directory) not in sys.path:
        sys.path.insert(0,str(directory))
    import collector_actions
    import collector_db_locality
    import collector_private_directories
    from scripts import collector_release
    return collector_actions,collector_db_locality,collector_private_directories,collector_release


def authorization(root,env):
    import re
    commit=env.get("MOSA_PRIVATE_EXPECTED_COMMIT","")
    if (root!=PROPOSED_ROOT or not re.fullmatch(r"[0-9a-f]{40}",commit)
        or env.get("MOSA_PRIVATE_UPLOAD_AUTHORIZATION")!=TOKEN+commit
        or env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_RUN_ATTEMPT")!="1"
        or not re.fullmatch(r"[1-9][0-9]{0,19}",env.get("GITHUB_RUN_ID",""))):
        raise PermissionError("EXPLICIT_COMMIT_BOUND_UPLOAD_AUTHORIZATION_REQUIRED")
    event,ref=env.get("GITHUB_EVENT_NAME"),env.get("GITHUB_REF")
    if not ((event=="workflow_dispatch" and ref=="refs/heads/main") or
            (event=="push" and ref=="refs/heads/codex/private-upload-live-a15aee")):
        raise PermissionError("UNAPPROVED_UPLOAD_TRIGGER")
    return commit


def artifact(project,commit):
    import hashlib
    unused,unused2,unused3,release=modules()
    archive,manifest=release.build(project,commit)
    meta=release.verify(project,commit,archive,manifest)
    if (len(meta["files"])!=33 or meta["payload_bytes"]!=248105 or
        hashlib.sha256(archive).hexdigest()!=ARCHIVE_SHA256):
        raise ValueError("QUALIFIED_PAYLOAD_CHANGED")
    contract,raw,files=release.payload(project,commit)
    return meta,manifest,files


def remote_source():
    from pathlib import Path
    unused,unused2,directories,unused3=modules()
    common=directories.REMOTE_SOURCE.split('if __name__=="__main__":')[0]
    extension=(Path(__file__).resolve().parent/"collector_private_upload_remote.py").read_text()
    return common+"\n"+extension


class RemoteRejected(ValueError):
    def __init__(self,result):
        super().__init__("REMOTE_UPLOAD_OPERATION_REJECTED")
        self.receipt={k:result[k] for k in ("failure","failure_type","errno") if k in result}


def call(transport,action,data):
    import shlex
    unused,remote,unused2,unused3=modules()
    wire=dict(data,action=action)
    cmd=shlex.join(["/opt/alt/python311/bin/python3.11","-I","-B","-c",remote_source()])
    code,out,errors,elapsed=remote.remote_call(transport,cmd,
        json.dumps(wire,separators=(",",":")).encode(),timeout=75)
    if code or errors:
        raise ValueError("REMOTE_UPLOAD_OPERATION_FAILED_NO_RETRY")
    result=json.loads(out)
    if result.get("ok") is not True:
        # Controlled helper codes only; never captured stderr or remote exception text.
        raise RemoteRejected(result)
    return result


def private_metadata(sftp):
    import stat
    base="/var/www/vhosts/web213.server10.configcenter.info"
    paths=["/","/var","/var/www","/var/www/vhosts",base,base+"/private",PROPOSED_ROOT]
    paths += [PROPOSED_ROOT+"/"+n for n in DIRECTORIES]
    for path in paths:
        s=sftp.lstat(path)
        if not stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode):
            raise ValueError("PRIVATE_PATH_TYPE")
        expected=(10317,1003,0o700) if path.startswith(base+"/private") else (
            (10317,1002,0o710) if path==base else (0,0,0o755))
        if (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))!=expected:
            raise ValueError("PRIVATE_OWNER_MODE")
    if sftp.normalize(PROPOSED_ROOT)!=PROPOSED_ROOT:
        raise ValueError("PRIVATE_CANONICAL_PATH")


def readback(sftp,path,manifest):
    """Independent bounded SFTP traversal/readback of only the manifest-owned tree."""
    import hashlib
    import stat
    from pathlib import PurePosixPath
    private_metadata(sftp)
    commit=manifest["commit"]
    if not (path==PROPOSED_ROOT+"/releases/"+commit or
            (path.startswith(PROPOSED_ROOT+"/staging/"+commit+"-") and
             re.fullmatch(r"[1-9][0-9]{0,19}",path.rsplit("-",1)[1]))):
        raise ValueError("READBACK_PATH")
    root=sftp.lstat(path)
    if (not stat.S_ISDIR(root.st_mode) or stat.S_ISLNK(root.st_mode) or
        (root.st_uid,root.st_gid,stat.S_IMODE(root.st_mode))!=(10317,1003,0o700)
        or sftp.normalize(path)!=path):
        raise ValueError("READBACK_ROOT")
    files={r["path"]:r for r in manifest["files"]}
    dirs={str(parent) for p in files for parent in PurePosixPath(p).parents if str(parent)!="."}
    pending=[""];seen_files=set();seen_dirs=set()
    while pending:
        rel=pending.pop()
        directory=path+("/"+rel if rel else "")
        children={p.split("/")[len(rel.split("/")) if rel else 0] for p in set(files)|dirs
                  if not rel or p.startswith(rel+"/")}
        seen=set()
        for entry in sftp.listdir_iter(directory,read_aheads=1):
            name=entry.filename
            if name not in children or name in seen:
                raise ValueError("UNKNOWN_REMOTE_FILE")
            seen.add(name)
            local=(rel+"/" if rel else "")+name
            full=path+"/"+local
            s=sftp.lstat(full)
            if stat.S_ISLNK(s.st_mode):
                raise ValueError("REMOTE_SYMLINK")
            if local in dirs:
                if not stat.S_ISDIR(s.st_mode) or (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))!=(10317,1003,0o700):
                    raise ValueError("REMOTE_DIRECTORY_MODE")
                seen_dirs.add(local);pending.append(local)
            else:
                row=files[local]
                if (not stat.S_ISREG(s.st_mode) or
                    (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode),s.st_size)!=(10317,1003,0o600,row["size"])):
                    raise ValueError("REMOTE_FILE_MODE_SIZE")
                with sftp.open(full,"rb") as source:
                    raw=source.read(row["size"]+1)
                    fd=source.stat()
                if (fd.st_uid,fd.st_gid,stat.S_IMODE(fd.st_mode),fd.st_size)!=(10317,1003,0o600,row["size"]):
                    raise ValueError("REMOTE_HANDLE_CHANGED")
                if len(raw)!=row["size"] or hashlib.sha256(raw).hexdigest()!=row["sha256"]:
                    raise ValueError("REMOTE_HASH_MISMATCH")
                seen_files.add(local)
        if seen!=children:
            raise ValueError("MISSING_REMOTE_FILE")
    if seen_files!=set(files) or seen_dirs!=dirs:
        raise ValueError("REMOTE_FILE_SET")
    return dict(status="PASS",files=len(seen_files),bytes=sum(r["size"] for r in files.values()),
                sha256="PASS",file_set="PASS",uid=10317,gid=1003,directories_mode="0700",files_mode="0600")


def upload(root=None,*,env=None,paramiko=None,**unexpected):
    import os
    if unexpected or root!=PROPOSED_ROOT or env is None:
        raise PermissionError("EXPLICIT_COMMIT_BOUND_UPLOAD_AUTHORIZATION_REQUIRED")
    commit=authorization(root,env)  # Before loading configuration, clients or reading files.
    from pathlib import Path
    import base64
    import hashlib
    import logging
    project=Path(__file__).resolve().parents[1]
    ssh,remote,unused,release=modules()
    if release.git(project,"rev-parse","HEAD").decode().strip()!=commit:
        raise PermissionError("CHECKOUT_COMMIT_MISMATCH")
    # Public repository main ref: source binding, never a remote hosting operation.
    current=release.git(project,"ls-remote","origin","refs/heads/main").decode().split()[0]
    if current!=commit:
        raise PermissionError("MAIN_COMMIT_MISMATCH")
    meta,manifest,files=artifact(project,commit)
    import deploy_test_sftp as profile
    config=profile.configuration(env)
    if paramiko is None:
        import paramiko
    logging.getLogger("paramiko").disabled=True
    data=dict(commit=commit,run_id=env["GITHUB_RUN_ID"],authorization=TOKEN+commit,manifest=meta,
              manifest_sha256=hashlib.sha256(manifest).hexdigest())
    report=dict(ok=False,commit=commit,release=root+"/releases/"+commit,collector_inactive=True,
                provider_requests=0,database_connections=0,automatic_retries=0,
                archive_sha256=ARCHIVE_SHA256,manifest_sha256=data["manifest_sha256"],
                manifest=meta,stage="prepare")
    try:
        status={}
        with ssh.ssh_client(config,status,paramiko) as transport:
            report["prepare_ssh"]=status
            prepared=call(transport,"prepare",dict(data,files={p:base64.b64encode(b).decode() for p,b in files.items()}))
            report["prepared"]=prepared
        report["stage"]="independent_staging_readback"
        status={}
        with ssh.ssh_client(config,status,paramiko) as transport:
            report["staging_ssh"]=status
            call(transport,"inspect",data)
            with paramiko.SFTPClient.from_transport(transport) as sftp:
                sftp.get_channel().settimeout(12)
                report["staging_readback"]=readback(sftp,prepared["staging"],meta)
        report["stage"]="atomic_publish"
        status={}
        with ssh.ssh_client(config,status,paramiko) as transport:
            report["publish_ssh"]=status
            report["published"]=call(transport,"publish",dict(data,
                stage_inode=prepared["stage_inode"],lock_inode=prepared["lock_inode"],
                independent_staging_readback=True))
        report["stage"]="independent_release_readback"
        status={}
        with ssh.ssh_client(config,status,paramiko) as transport:
            report["release_ssh"]=status
            call(transport,"inspect",data)
            with paramiko.SFTPClient.from_transport(transport) as sftp:
                sftp.get_channel().settimeout(12)
                report["release_readback"]=readback(sftp,report["release"],meta)
        report["ok"]=True;report["stage"]="complete"
    except Exception as error:
        report["failure_type"]=type(error).__name__
        if isinstance(error,RemoteRejected):report["remote_failure"]=error.receipt
        report["no_retry_or_cleanup"]=True
    return report


def main():
    import os
    import sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation",choices=("plan","upload"))
    args=parser.parse_args()
    if args.operation=="plan":
        print(json.dumps(proposal(PROPOSED_ROOT,())))
        return 0
    ssh,unused,unused2,unused3=modules()
    try:report=upload(PROPOSED_ROOT,env=os.environ)
    except Exception as error:
        report=dict(ok=False,failure_type=type(error).__name__,collector_inactive=True)
    text=ssh.public_text(report,os.environ)
    print(text,flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as stream:
            stream.write("MOSA-2 one-shot PRIVATE release receipt (collector inactive)\n\n")
            stream.write("~~~json\n"+text+"\n~~~\n")
    return 0 if report["ok"] and json.loads(text).get("ok") else 1


if __name__=="__main__":
    raise SystemExit(main())
