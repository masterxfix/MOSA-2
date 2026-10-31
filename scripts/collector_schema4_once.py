"""One explicitly approved schema-4 request, private publication and shared Current projection."""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from scripts import collector_release as release, deploy_private_collector as upload
from scripts.collector_schema4_once_remote import complete
import collector_actions as shared
import collector_db_locality as remote

TOKEN = upload.SCHEMA4_TOKEN
ONCE = "schema4-live-20261030"
CLEAN_ENV = dict(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin", PYTHONDONTWRITEBYTECODE="1")
PHP = "/opt/plesk/php/8.4/bin/php"
PYTHON = "/opt/alt/python311/bin/python3.11"

# Fileless, local-only measurement under exactly the supervisor's requested environment.
# CPython ssl documents lazy capath loading; OpenSSL documents hash.N lookup names.
# The diagnostic context below parses existing default-source certificates only.
# It never replaces the HTTPS transport's default trust store or verifies a peer.
RUNTIME_PROBE = r'''
import json, os, re, ssl, stat, subprocess, sys, time
CLEAN_ENV = dict(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin", PYTHONDONTWRITEBYTECODE="1")
PHP = "/opt/plesk/php/8.4/bin/php"

def ca_source(context, paths):
    result = dict(ca_source_verified=False, ca_source_kind="UNAVAILABLE",
        ca_source_scope="LOCAL_SOURCE_ONLY_NOT_PROVIDER_TLS", ca_file=paths.cafile,
        ca_path=paths.capath, ca_path_entry=None, ca_entries_examined=0,
        ca_candidates_checked=0, ca_failure_code="NO_USABLE_DEFAULT_CA_SOURCE")
    if context.cert_store_stats()["x509_ca"] > 0:
        result.update(ca_source_verified=True, ca_source_kind="DEFAULT_CONTEXT_LOADED", ca_failure_code=None)
        return result
    def parsed(path):
        try:
            info = os.stat(path)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 4*1024*1024:
                return False
            diagnostic = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            diagnostic.load_verify_locations(cafile=path)
            return diagnostic.cert_store_stats()["x509_ca"] > 0
        except (OSError, ssl.SSLError, ValueError):
            return False
    if paths.cafile and parsed(paths.cafile):
        result.update(ca_source_verified=True, ca_source_kind="DEFAULT_CAFILE_PARSED", ca_failure_code=None)
        return result
    if not paths.capath:
        return result
    # A directory address alone is insufficient. Check at least one real CA
    # certificate with its OpenSSL subject hash matching the configured hash.0
    # lookup entry. No directory recursion, new trust store or network request.
    deadline = time.monotonic()+10
    try:
        with os.scandir(paths.capath) as entries:
            for entry in entries:
                if result["ca_entries_examined"] >= 512 or time.monotonic() >= deadline:
                    result["ca_failure_code"] = "LOCAL_CA_PROOF_BUDGET"
                    break
                result["ca_entries_examined"] += 1
                match = re.fullmatch(r"([0-9a-f]{8})\.0", entry.name)
                if not match:
                    continue
                if result["ca_candidates_checked"] >= 8:
                    result["ca_failure_code"] = "LOCAL_CA_PROOF_BUDGET"
                    break
                result["ca_candidates_checked"] += 1
                if not parsed(entry.path):
                    continue
                try:
                    child = subprocess.run(["/usr/bin/openssl", "x509", "-in", entry.path,
                        "-subject_hash", "-noout"], stdin=subprocess.DEVNULL,
                        capture_output=True, timeout=2, env=CLEAN_ENV)
                except (OSError, subprocess.TimeoutExpired):
                    result["ca_failure_code"] = "LOCAL_CA_HASH_CHECK_UNAVAILABLE"
                    break
                if child.returncode == 0 and not child.stderr and child.stdout.strip() == match[1].encode():
                    result.update(ca_source_verified=True, ca_source_kind="DEFAULT_CAPATH_HASH_ENTRY_PARSED",
                                  ca_path_entry=entry.name, ca_failure_code=None)
                    break
    except OSError:
        result["ca_failure_code"] = "DEFAULT_CAPATH_UNREADABLE"
    return result

def probe():
    r = dict(version=".".join(map(str,sys.version_info[:3])), executable=sys.executable,
        resolved_executable=os.path.realpath(sys.executable), berlin=None,
        loaded_ca=None, loaded_x509=None, verify_mode=None, check_hostname=None,
        ca_source_verified=False, ca_source_kind="UNAVAILABLE", ca_file=None, ca_path=None,
        ca_path_entry=None, ca_entries_examined=0, ca_candidates_checked=0, ca_paths_measured=False,
        ca_failure_code="DEFAULT_CONTEXT_UNAVAILABLE", ca_source_scope="LOCAL_SOURCE_ONLY_NOT_PROVIDER_TLS",
        provider_tls="NOT_CHECKED", php_child=None,
        ssl_environment_overrides_absent=not any(k in os.environ for k in
            ("SSL_CERT_FILE","SSL_CERT_DIR","SSLKEYLOGFILE")))
    try:
        import zoneinfo
        r["berlin"] = str(zoneinfo.ZoneInfo("Europe/Berlin")) == "Europe/Berlin"
    except Exception:
        r["berlin"] = False
    try:
        context = ssl.create_default_context()
        r.update(loaded_ca=context.cert_store_stats()["x509_ca"],
            loaded_x509=context.cert_store_stats()["x509"],
            verify_mode="CERT_REQUIRED" if context.verify_mode == ssl.CERT_REQUIRED else "OTHER",
            check_hostname=context.check_hostname)
        paths = ssl.get_default_verify_paths()
        r["ca_paths_measured"] = True
        r.update(ca_source(context, paths))
    except (OSError, ssl.SSLError, ValueError):
        pass
    try:
        child = subprocess.run([PHP,"-r",'echo json_encode(["version"=>PHP_VERSION,"binary"=>PHP_BINARY]);'],
            capture_output=True, timeout=5, env=CLEAN_ENV)
        if child.returncode == 0 and not child.stderr:
            r["php_child"] = json.loads(child.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return r

if __name__ == "__main__":
    print(json.dumps(probe(),sort_keys=True))
'''


class RuntimeRejected(ValueError):
    """Only fixed runtime error codes, with measurements retained by the caller."""


def clean_command(args):
    return shlex.join(["/usr/bin/env", "-i", *(k+"="+v for k,v in CLEAN_ENV.items()), *args])


def runtime_decision(result):
    p, q = result["php"], result["python"]
    rules = [
        ("PHP_VERSION_MISMATCH", p["version"], p["expected_version"]),
        ("PHP_CLI_REQUIRED", p["sapi"], "cli"),
        ("PHP_PDO_MYSQL_REQUIRED", p["pdo_mysql"], True),
        ("PHP_BINARY_MISMATCH", p["binary"], PHP),
        ("PYTHON_VERSION_MISMATCH", q["version"], q["expected_version"]),
        ("PYTHON_BINARY_MISMATCH", q["executable"], PYTHON),
        ("BERLIN_TIMEZONE_UNAVAILABLE", q["berlin"], True),
        ("TLS_CERT_REQUIRED", q["verify_mode"], "CERT_REQUIRED"),
        ("TLS_HOSTNAME_REQUIRED", q["check_hostname"], True),
        ("DEFAULT_CA_SOURCE_UNAVAILABLE", q["ca_source_verified"], True),
        ("SSL_ENVIRONMENT_NOT_CLEAN", q["ssl_environment_overrides_absent"], True),
        ("PHP_CHILD_VERSION_MISMATCH", q["php_child"]["version"], p["expected_version"]),
        ("PHP_CHILD_BINARY_MISMATCH", q["php_child"]["binary"], PHP),
    ]
    result["checks"] = {name: "NOT_MEASURED" if actual is None else
                         "PASS" if type(actual) is type(expected) and actual == expected else "FAIL"
                         for name,actual,expected in rules}
    result["failure_code"] = next((name for name,_,_ in rules if result["checks"][name] != "PASS"), None)
    return result["failure_code"] is None


def authorize(env):
    commit = env.get("MOSA_SCHEMA4_EXPECTED_COMMIT", "")
    if (not re.fullmatch(r"[a-f0-9]{40}", commit)
            or env.get("MOSA_SCHEMA4_AUTHORIZATION") != TOKEN + commit
            or env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_REPOSITORY") != "masterxfix/MOSA-2"
            or env.get("GITHUB_SHA") != commit
            or not re.fullmatch(r"[1-9][0-9]{0,19}", env.get("GITHUB_RUN_ID", ""))):
        raise PermissionError("EXACT_SCHEMA4_ONE_SHOT_AUTHORIZATION_REQUIRED")
    return commit, "schema4-" + commit + "-" + env["GITHUB_RUN_ID"]


def runtime(transport, expected, result=None):
    """Retain allowlisted measurements before any decision, including a rejection."""
    result = {} if result is None else result
    result.clear()
    result.update(null_means="NOT_MEASURED", requested_environment=dict(CLEAN_ENV), provider_requests=0,
        php=dict(expected_version=expected["php_version"], intended_binary=PHP, version=None, binary=None, sapi=None, pdo_mysql=None),
        python=dict(expected_version=expected["python_version"], intended_binary=PYTHON, version=None, executable=None,
            resolved_executable=None, berlin=None, loaded_ca=None, loaded_x509=None,
            verify_mode=None, check_hostname=None, ca_source_verified=None, ca_source_kind=None,
            ca_file=None, ca_path=None, ca_path_entry=None, ca_entries_examined=None,
            ca_candidates_checked=None, ca_failure_code=None, ca_paths_measured=None, ssl_environment_overrides_absent=None,
            ca_source_scope="LOCAL_SOURCE_ONLY_NOT_PROVIDER_TLS", provider_tls="NOT_CHECKED",
            php_child=dict(version=None, binary=None)))
    runtime_decision(result)
    def reject(code):
        runtime_decision(result)
        result["failure_code"] = code
        raise RuntimeRejected(code)
    def version(value):
        return value if type(value) is str and re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,3}){2}", value) else None
    def path(value):
        return value if type(value) is str and len(value)<=1024 and re.fullmatch(r"/[A-Za-z0-9_./:+-]+",value) else None
    capability = ('echo json_encode(["version"=>PHP_VERSION,"binary"=>PHP_BINARY,"sapi"=>PHP_SAPI,'
                  '"pdo_mysql"=>class_exists("PDO")&&in_array("mysql",PDO::getAvailableDrivers(),true)]);')
    command = shlex.split(remote.command(PHP, capability))
    try:
        code, out, err, _ = remote.remote_call(transport, clean_command(command), timeout=25)
    except Exception:
        reject("PHP_PROBE_FAILED")
    if code or err:
        reject("PHP_PROBE_FAILED")
    try:
        p = json.loads(out)
        if not isinstance(p,dict):
            raise ValueError()
    except (ValueError, TypeError):
        reject("PHP_PROBE_OUTPUT_INVALID")
    result["php"].update(version=version(p.get("version")), binary=path(p.get("binary")),
        sapi=p.get("sapi") if p.get("sapi") in ("cli","fpm-fcgi","cgi-fcgi") else None,
        pdo_mysql=p.get("pdo_mysql") if type(p.get("pdo_mysql")) is bool else None)
    runtime_decision(result)
    try:
        code, out, err, _ = remote.remote_call(transport, clean_command([PYTHON,"-I","-B","-c",RUNTIME_PROBE]), timeout=25)
    except Exception:
        reject("PYTHON_PROBE_FAILED")
    if code or err:
        reject("PYTHON_PROBE_FAILED")
    try:
        raw = json.loads(out)
        if not isinstance(raw,dict):
            raise ValueError()
    except (ValueError, TypeError):
        reject("PYTHON_PROBE_OUTPUT_INVALID")
    q = result["python"]
    q.update(version=version(raw.get("version")), executable=path(raw.get("executable")),
             resolved_executable=path(raw.get("resolved_executable")),
             ca_file=path(raw.get("ca_file")), ca_path=path(raw.get("ca_path")))
    for key in ("berlin","check_hostname","ca_source_verified","ssl_environment_overrides_absent","ca_paths_measured"):
        if type(raw.get(key)) is bool:
            q[key] = raw[key]
    if q["ca_paths_measured"] is True:
        for key in ("ca_file","ca_path"):
            if raw.get(key) is None:
                q[key] = "NOT_CONFIGURED"
    for key in ("loaded_ca","loaded_x509","ca_entries_examined","ca_candidates_checked"):
        if type(raw.get(key)) is int and 0 <= raw[key] <= 100000:
            q[key] = raw[key]
    enums = dict(verify_mode={"CERT_REQUIRED","OTHER"},
        ca_source_kind={"UNAVAILABLE","DEFAULT_CONTEXT_LOADED","DEFAULT_CAFILE_PARSED","DEFAULT_CAPATH_HASH_ENTRY_PARSED"},
        ca_failure_code={"NO_USABLE_DEFAULT_CA_SOURCE","LOCAL_CA_PROOF_BUDGET","LOCAL_CA_HASH_CHECK_UNAVAILABLE",
                         "DEFAULT_CAPATH_UNREADABLE","DEFAULT_CONTEXT_UNAVAILABLE"})
    for key, allowed in enums.items():
        if type(raw.get(key)) is str and raw[key] in allowed:
            q[key] = raw[key]
    entry = raw.get("ca_path_entry")
    if type(entry) is str and re.fullmatch(r"[0-9a-f]{8}\.0",entry):
        q["ca_path_entry"] = entry
    child = raw.get("php_child")
    if isinstance(child,dict):
        q["php_child"].update(version=version(child.get("version")), binary=path(child.get("binary")))
    if not runtime_decision(result):
        raise RuntimeRejected(result["failure_code"])
    return result


def remote_source(manifest):
    # Reuse the no-follow private auditor and the existing bounded process supervisor.
    base = upload.remote_source("schema4-once", manifest).split('if __name__=="__main__":')[0]
    supervisor = (ROOT / "scripts/collector_dogado_pne_remote.py").read_text().split('if __name__=="__main__":')[0]
    extension = (ROOT / "scripts/collector_schema4_once_remote.py").read_text()
    return base + "\n" + supervisor + "\n" + extension


def execute(env, paramiko=None):
    commit, run = authorize(env)
    config = shared.configuration(env)  # Names-only missing-secret checks before any remote operation.
    if release.git(ROOT, "rev-parse", "HEAD").decode().strip() != commit:
        raise PermissionError("CHECKOUT_COMMIT_MISMATCH")
    if release.git(ROOT, "ls-remote", "origin", "refs/heads/main").decode().split()[0] != commit:
        raise PermissionError("MAIN_COMMIT_MISMATCH")
    manifest, wire, _ = upload.artifact(ROOT, commit, "schema4-once")
    if paramiko is None:
        import paramiko
    logging.getLogger("paramiko").disabled = True
    report = dict(ok=False, status="NOT_STARTED", commit=commit, run=run,
                  release=upload.PROPOSED_ROOT + "/releases/" + commit,
                  provider_requests=0, automatic_retries=0, scheduler_enabled=False,
                  provider_rights="NOT_ATTESTED", stage="runtime", runtime={})
    dispatched = False
    try:
        status = {}
        with shared.ssh_client(config, status, paramiko) as transport:
            report["ssh"] = status
            runtime(transport, manifest["runtime"], report["runtime"])
        report["stage"] = "private_installation"
        upload_env = dict(env, MOSA_PRIVATE_EXPECTED_COMMIT=commit,
                          MOSA_PRIVATE_UPLOAD_AUTHORIZATION=TOKEN + commit)
        report["installation"] = upload.upload(upload.PROPOSED_ROOT, env=upload_env,
                                               paramiko=paramiko, profile="schema4-once")
        if not report["installation"]["ok"]:
            return report
        data = dict(commit=commit, run=run, run_id=env["GITHUB_RUN_ID"], authorization=TOKEN + commit,
                    manifest=manifest, manifest_sha256=hashlib.sha256(wire).hexdigest(),
                    private_path_identity=report["installation"]["private_path_identity"],
                    password=env["MOSA_TEST_DB_PASSWORD"])
        report["stage"] = "one_shot"
        with shared.ssh_client(config, {}, paramiko) as transport:
            command = shlex.join(["/opt/alt/python311/bin/python3.11", "-I", "-B", "-c", remote_source(manifest)])
            dispatched = True
            code, out, err, _ = remote.remote_call(transport, command,
                json.dumps(data, separators=(",", ":")).encode(), timeout=180)
            if code or err:
                raise ValueError("ONE_SHOT_RESULT_UNKNOWN_NO_RETRY")
            result = json.loads(out)
            report["result"] = result
            if result.get("ok") is True and not complete(result):
                raise ValueError("ONE_SHOT_RESULT_UNKNOWN_NO_RETRY")
            report["status"] = result["status"]
            report["provider_requests"] = result.get("provider_requests")
            report["ok"] = complete(result)
            if report["status"] == "OUTCOME_UNKNOWN":
                report["read_only_reconciliation_required"] = True
        report["stage"] = "finished"
    except Exception as error:
        report["ok"] = False
        report["failure_type"] = type(error).__name__
        if isinstance(error, RuntimeRejected):
            report["failure"] = "RUNTIME_" + report["runtime"]["failure_code"]
        elif isinstance(error, ValueError) and str(error) == "ONE_SHOT_RESULT_UNKNOWN_NO_RETRY":
            report["failure"] = str(error)
        if dispatched:
            report.update(status="OUTCOME_UNKNOWN", provider_requests=None, read_only_reconciliation_required=True)
    return report


def main():
    try:
        report = execute(os.environ)
    except shared.ConfigurationError as error:
        report = dict(ok=False, status="NOT_STARTED", provider_requests=0, failure=str(error))
    except Exception as error:
        report = dict(ok=False, status="NOT_STARTED", provider_requests=0, failure_type=type(error).__name__)
    text = shared.public_text(report, os.environ)
    print(text, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write("Schema-4 one-shot receipt; automatic operation remains disabled\n\n~~~json\n" + text + "\n~~~\n")
    return 0 if (report["ok"] and report["status"] == "COMPLETE"
                 and complete(report.get("result")) and json.loads(text).get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
