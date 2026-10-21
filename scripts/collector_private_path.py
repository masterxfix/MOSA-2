"""Read-only, finite-path private-root metadata assessment. No deployment capability."""
import errno
import json
import logging
import os
from pathlib import Path
import shlex
import stat
import sys
import time

import collector_actions as shared
import collector_db_locality as remote
import deploy_test_sftp as profile

ROOT = Path(__file__).resolve().parents[1]
HOST_ROOT = "/var/www/vhosts/web213.server10.configcenter.info"
PRIVATE_ROOT = HOST_ROOT + "/private/mosa2-collector"
TEST_ROOT = HOST_ROOT + "/mosa2-test.scharwerk.de"
PYTHON = "/opt/alt/python311/bin/python3.11"
CHAIN = ("/", "/var", "/var/www", "/var/www/vhosts", HOST_ROOT,
         HOST_ROOT + "/private", PRIVATE_ROOT)
# This is a one-task READ authorization only. It cannot enable private deployment.
READ_AUTHORIZATION = "mosa2-private-path-metadata-only-2026-10-21"

REMOTE_SOURCE = r'''
import errno
import json
import os
import stat
import sys
H = "/var/www/vhosts/web213.server10.configcenter.info"
P = H + "/private/mosa2-collector"
W = H + "/mosa2-test.scharwerk.de"
CHAIN = ("/", "/var", "/var/www", "/var/www/vhosts", H, H+"/private", P)

def node(api, path):
    try:
        s = api.lstat(path)
        kind = "directory" if stat.S_ISDIR(s.st_mode) else "symlink" if stat.S_ISLNK(s.st_mode) else "other"
        return dict(path=path, status="PRESENT", kind=kind, uid=s.st_uid, gid=s.st_gid,
                    mode=format(stat.S_IMODE(s.st_mode), "04o"), size=s.st_size,
                    mtime=int(s.st_mtime), device=s.st_dev, inode=s.st_ino)
    except OSError as e:
        status = {errno.ENOENT:"MISSING", errno.EACCES:"DENIED", errno.EPERM:"DENIED",
                  errno.ENOTDIR:"NOT_DIRECTORY"}.get(e.errno, "ERROR")
        return dict(path=path, status=status)

def walk(api, paths):
    out = []
    for path in paths:
        row = node(api, path)
        out.append(row)
        if row["status"] != "PRESENT" or row["kind"] != "directory":
            break
    return out

def assess(api, context):
    r = dict(complete=True, cwd=api.getcwd(), uid=api.getuid(), gid=api.getgid(),
             effective_uid=api.geteuid(), effective_gid=api.getegid(),
             full_chain=walk(api, CHAIN), selected_view=None, selected_chain=[],
             test_webroot=None, capacity=None, mapping_basis=None)
    if any(v["status"] not in ("PRESENT", "MISSING") or v.get("kind", "directory") != "directory"
           for v in r["full_chain"]):
        r["blocker"] = "SSH_PATH_BOUNDARY_STOP"
        return r
    bypath = {v["path"]:v for v in r["full_chain"]}
    anchor = bypath.get(H)
    if anchor and anchor["status"] == "PRESENT" and anchor["kind"] == "directory":
        r["selected_view"] = "HOST_ABSOLUTE"
        r["selected_chain"] = r["full_chain"]
        r["mapping_basis"] = "HOST_PATH_VISIBLE"
        # This sibling is already the explicitly documented MOSA-2 test webroot.
        if all(v["status"] in ("PRESENT", "MISSING") and v.get("kind", "directory") == "directory"
               for v in r["selected_chain"]):
            r["test_webroot"] = node(api, W)
    elif (r["full_chain"][-1]["status"] == "MISSING"
          and r["cwd"] == "/" and context == H):
        # Only an ENOENT namespace difference permits this finite chroot alias.
        # DENIED/symlink/other types never trigger an alternate path.
        r["selected_view"] = "CHROOT_RELATIVE"
        r["selected_chain"] = walk(api, ("/", "/private", "/private/mosa2-collector"))
        r["mapping_basis"] = "CWD_ROOT_AND_SFTP_CANONICAL_ACCOUNT_ANCHOR"
        if all(v["status"] in ("PRESENT", "MISSING") and v.get("kind", "directory") == "directory"
               for v in r["selected_chain"]):
            r["test_webroot"] = node(api, "/mosa2-test.scharwerk.de")
    chain = r["selected_chain"]
    if chain and all(v["status"] in ("PRESENT", "MISSING") and
                     (v["status"] != "PRESENT" or v["kind"] == "directory") for v in chain):
        nearest = next((v["path"] for v in reversed(chain) if v["status"] == "PRESENT"), None)
        if nearest:
            try:
                v = api.statvfs(nearest)
                r["capacity"] = dict(path=nearest, fragment_size=v.f_frsize,
                    total_bytes=v.f_blocks*v.f_frsize, free_bytes=v.f_bfree*v.f_frsize,
                    available_bytes=v.f_bavail*v.f_frsize, total_inodes=v.f_files,
                    free_inodes=v.f_ffree, available_inodes=v.f_favail,
                    hosting_quota="UNCONFIRMED")
            except OSError as e:
                r["capacity"] = dict(path=nearest, status="DENIED" if e.errno in
                                    (errno.EACCES,errno.EPERM) else "UNAVAILABLE")
    return r

if __name__ == "__main__":
    context = json.loads(sys.stdin.read()).get("sftp_anchor")
    if context not in (H, None):
        raise ValueError("invalid context")
    print(json.dumps(assess(os, context), sort_keys=True))
'''


def fields(path, s):
    return dict(path=path, status="PRESENT", kind="directory" if stat.S_ISDIR(s.st_mode)
                else "symlink" if stat.S_ISLNK(s.st_mode) else "other",
                uid=s.st_uid, gid=s.st_gid, mode=format(stat.S_IMODE(s.st_mode), "04o"),
                size=s.st_size, mtime=int(s.st_mtime))


def sftp_probe(sftp, clock=time.monotonic):
    deadline = clock()+45

    def call(method, path):
        remaining = deadline-clock()
        if remaining <= 0:
            raise remote.ProbeError("SFTP_METADATA_BUDGET")
        sftp.get_channel().settimeout(min(8, remaining))
        return getattr(sftp, method)(path)

    rows = []
    for path in CHAIN:
        try:
            row = fields(path, call("lstat", path))
        except OSError as e:
            row = dict(path=path, status={errno.ENOENT:"MISSING", errno.EACCES:"DENIED",
                errno.EPERM:"DENIED", errno.ENOTDIR:"NOT_DIRECTORY"}.get(e.errno, "ERROR"))
        rows.append(row)
        if row["status"] != "PRESENT" or row["kind"] != "directory":
            break
    out = dict(chain=rows, anchor=None, start_directory=None, test_webroot=None)
    if any(v["status"] not in ("PRESENT", "MISSING") or v.get("kind", "directory") != "directory"
           for v in rows):
        return out
    # Normalize only already lstat-checked non-link directories. No directory listing.
    account = next((v for v in rows if v["path"] == HOST_ROOT), None)
    if account and account["status"] == "PRESENT" and account["kind"] == "directory":
        canonical = call("normalize", HOST_ROOT)
        if canonical != HOST_ROOT:
            raise remote.ProbeError("SFTP_ACCOUNT_CANONICAL_MISMATCH")
        out["anchor"] = canonical
        # Current-directory normalization supplies mapping context only, never a probe target.
        start = call("normalize", ".")
        out["start_directory"] = start if start in ("/", HOST_ROOT) else "UNEXPECTED_START_NOT_INSPECTED"
        try:
            out["test_webroot"] = fields(TEST_ROOT, call("lstat", TEST_ROOT))
        except OSError as e:
            out["test_webroot"] = dict(path=TEST_ROOT, status="DENIED" if e.errno in
                                      (errno.EACCES, errno.EPERM) else "UNAVAILABLE")
    return out


def compare(ssh, sftp):
    left = ssh["selected_chain"]
    right = sftp["chain"]
    if not left or not right:
        return dict(path_views="UNCONFIRMED", webroot_isolation="UNCONFIRMED",
                    all_webroots_and_public_urls="UNCONFIRMED")
    def logical(path):
        if path == HOST_ROOT:return "account"
        if path.startswith(HOST_ROOT+"/"):return path[len(HOST_ROOT):]
        if path == "/":return "account" if ssh["selected_view"] == "CHROOT_RELATIVE" else "/"
        return path
    lmap = {logical(v["path"]):v for v in left}
    # SFTP always uses the already documented absolute host namespace.
    rmap = {("account" if v["path"] == HOST_ROOT else v["path"][len(HOST_ROOT):]
             if v["path"].startswith(HOST_ROOT+"/") else v["path"]):v for v in right}
    comparisons = {}
    for key in ("account", "/private", "/private/mosa2-collector"):
        a, b = lmap.get(key), rmap.get(key)
        if a is None or b is None:
            comparisons[key] = "NOT_REACHED"
        elif a["status"] == b["status"] == "MISSING":
            comparisons[key] = "MATCH_MISSING"
        elif a["status"] == b["status"] == "PRESENT" and all(
                a[k] == b[k] for k in ("kind", "uid", "gid", "mode", "size", "mtime")):
            comparisons[key] = "MATCH_METADATA"
        else:
            comparisons[key] = "MISMATCH_OR_DENIED"
    matched = all(v in ("MATCH_METADATA", "MATCH_MISSING", "NOT_REACHED") for v in comparisons.values())
    matched = matched and comparisons["account"] == "MATCH_METADATA"
    symlink = any(v.get("kind") == "symlink" for v in left+right)
    block = any(v["status"] not in ("PRESENT", "MISSING") or v.get("kind", "directory") != "directory"
                for v in left+right)
    a, b = ssh.get("test_webroot"), sftp.get("test_webroot")
    web_match = bool(a and b and a["status"] == b["status"] == "PRESENT"
                     and a["kind"] == b["kind"] == "directory"
                     and all(a[k] == b[k] for k in ("uid", "gid", "mode", "size", "mtime")))
    # Evidence is for this documented sibling only; absent targets get a prospective result.
    private_nodes = [lmap[k] for k in ("/private", "/private/mosa2-collector")
                     if k in lmap and lmap[k]["status"] == "PRESENT"]
    alias = bool(a and a.get("status") == "PRESENT" and any(
        v.get("device") == a.get("device") and v.get("inode") == a.get("inode") for v in private_nodes))
    isolation = "FAIL" if symlink or alias else "PASS" if matched and web_match and not block else "UNCONFIRMED"
    return dict(path_views="MATCH_METADATA" if matched and not block else "UNCONFIRMED",
                comparisons=comparisons, sftp_inode_identity="NOT_EXPOSED_BY_SFTP_V3",
                webroot_isolation=isolation, webroot_scope="KNOWN_MOSA2_TEST_WEBROOT_ONLY",
                all_webroots_and_public_urls="UNCONFIRMED")


def execute(env, paramiko=None):
    report = dict(ok=False, stage="configuration", ssh="NOT_CHECKED", host_key="NOT_CHECKED",
                  read_authorization=READ_AUTHORIZATION, private_root=PRIVATE_ROOT,
                  remote_writes=0, directory_listings=0, database_connections=0, provider_requests=0,
                  deployment_enabled=False)
    try:
        # Reuse the two-secret SFTP profile; no DB secret is required or requested.
        config = profile.configuration(env)
        if paramiko is None:
            import paramiko
        logging.getLogger("paramiko").disabled = True
        report["stage"] = "ssh"
        with shared.ssh_client(config, report, paramiko) as transport:
            report["stage"] = "sftp_metadata"
            with paramiko.SFTPClient.from_transport(transport) as sftp:
                report["sftp"] = sftp_probe(sftp)
            # A permission boundary or link is not bypassed by a different protocol.
            if any(v["status"] not in ("PRESENT", "MISSING") or v.get("kind", "directory") != "directory"
                   for v in report["sftp"]["chain"]):
                report["blocker"] = "SFTP_PATH_BOUNDARY_STOP"
                report["ok"] = True
                return report
            report["stage"] = "ssh_metadata"
            cmd = shlex.join([PYTHON, "-I", "-B", "-c", REMOTE_SOURCE])
            data = json.dumps(dict(sftp_anchor=report["sftp"]["anchor"])).encode()
            code, output, errors, elapsed = remote.remote_call(transport, cmd, data, timeout=30)
            if code or errors:
                raise remote.ProbeError("SSH_METADATA_PROCESS_FAILED")
            result = json.loads(output)
            if not isinstance(result, dict) or result.get("complete") is not True:
                raise remote.ProbeError("SSH_METADATA_RESULT_INVALID")
            report["ssh_metadata"] = result
            report["comparison"] = compare(result, report["sftp"])
            report["elapsed_ms"] = elapsed
            report["ok"] = True
        report["stage"] = "finished"
    except ValueError:
        report["failure"] = "INVALID_CONFIGURATION_OR_METADATA"
    except remote.ProbeError as error:
        report["failure"] = str(error)
    except Exception as error:
        report["failure_type"] = type(error).__name__
    return report


def main():
    report = execute(os.environ)
    text = shared.public_text(report, os.environ)
    print(text, flush=True)
    return 0 if report["ok"] and json.loads(text).get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
