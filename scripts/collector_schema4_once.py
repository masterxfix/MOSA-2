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
import collector_actions as shared
import collector_db_locality as remote

TOKEN = upload.SCHEMA4_TOKEN
ONCE = "schema4-live-20261030"


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


def runtime(transport):
    """Measure the two exact existing binaries before installation; never search/install/downgrade."""
    php = "/opt/plesk/php/8.4/bin/php"
    python = "/opt/alt/python311/bin/python3.11"
    code, out, err, _ = remote.remote_call(transport, remote.command(php, remote.CAPABILITY), timeout=25)
    if code or err:
        raise ValueError("PINNED_PHP_UNAVAILABLE")
    p = json.loads(out)
    probe = ('import json,sys,ssl,zoneinfo,dataclasses,typing,subprocess,os;'
             'child=subprocess.run(["/opt/plesk/php/8.4/bin/php","-r",'
             '\'echo json_encode(["version"=>PHP_VERSION,"binary"=>PHP_BINARY]);\'],'
             'capture_output=True,timeout=5,env=dict(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin"));'
             'print(json.dumps(dict(version=".".join(map(str,sys.version_info[:3])),'
             'executable=sys.executable,berlin=str(zoneinfo.ZoneInfo("Europe/Berlin")),'
             'ca=ssl.create_default_context().cert_store_stats()["x509_ca"],'
             'php_child=json.loads(child.stdout) if child.returncode==0 and not child.stderr else None)))')
    code, out, err, _ = remote.remote_call(transport, shlex.join([python, "-I", "-B", "-c", probe]), timeout=25)
    if code or err:
        raise ValueError("PINNED_PYTHON_UNAVAILABLE")
    q = json.loads(out)
    if p.get("version") != "8.4.12" or p.get("sapi") != "cli" or not p.get("pdo_mysql"):
        raise ValueError("MEASURED_PHP_OUTSIDE_QUALIFIED_RUNTIME")
    if q.get("version") != "3.11.17" or q.get("berlin") != "Europe/Berlin" or q.get("ca", 0) < 1:
        raise ValueError("MEASURED_PYTHON_OUTSIDE_QUALIFIED_RUNTIME")
    if q.get("php_child") != dict(version="8.4.12", binary=php):
        raise ValueError("MEASURED_PHP_OUTSIDE_QUALIFIED_RUNTIME")
    return dict(php=p, python=q, provider_requests=0)


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
                  provider_rights="NOT_ATTESTED", stage="runtime")
    dispatched = False
    try:
        status = {}
        with shared.ssh_client(config, status, paramiko) as transport:
            report["ssh"] = status
            report["runtime"] = runtime(transport)
        report["stage"] = "private_installation"
        upload_env = dict(env, MOSA_PRIVATE_EXPECTED_COMMIT=commit,
                          MOSA_PRIVATE_UPLOAD_AUTHORIZATION=TOKEN + commit)
        report["installation"] = upload.upload(upload.PROPOSED_ROOT, env=upload_env,
                                               paramiko=paramiko, profile="schema4-once")
        if not report["installation"]["ok"]:
            return report
        data = dict(commit=commit, run=run, run_id=env["GITHUB_RUN_ID"], authorization=TOKEN + commit,
                    manifest=manifest, manifest_sha256=hashlib.sha256(wire).hexdigest(),
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
            report["status"] = result["status"]
            report["provider_requests"] = result.get("provider_requests")
            report["ok"] = result.get("ok") is True
        report["stage"] = "finished"
    except Exception as error:
        report["failure_type"] = type(error).__name__
        if isinstance(error, ValueError) and str(error) in {
                "PINNED_PHP_UNAVAILABLE", "PINNED_PYTHON_UNAVAILABLE",
                "MEASURED_PHP_OUTSIDE_QUALIFIED_RUNTIME", "MEASURED_PYTHON_OUTSIDE_QUALIFIED_RUNTIME",
                "ONE_SHOT_RESULT_UNKNOWN_NO_RETRY"}:
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
    return 0 if report["ok"] and json.loads(text).get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
