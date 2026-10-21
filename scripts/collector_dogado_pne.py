"""Explicitly authorized one-PNE local collector start; no upload or retry."""
import ast
from datetime import datetime,timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shlex
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from scripts import collector_release as release
from scripts import deploy_private_collector as private
import collector_actions as shared
import collector_db_locality as remote
import collector_private_directories as directories

RELEASE_COMMIT="92274a79550b8acd719434459022da6de5261d2e"
PRIVATE=private.PROPOSED_ROOT
RELEASE=PRIVATE+"/releases/"+RELEASE_COMMIT
ONCE="first-live-PNE-DE000A0JBPG2-"+RELEASE_COMMIT
RUN=PRIVATE+"/runs/"+ONCE
TOKEN="MOSA2-PNE-SECOND-LIVE-20261021:"
SECOND_PREFIX="second-live-PNE-DE000A0JBPG2-"

def run_name(commit):
    if not re.fullmatch(r"[0-9a-f]{40}",commit):raise ValueError("RUN_COMMIT")
    return SECOND_PREFIX+commit

def run_directory(commit):
    return PRIVATE+"/runs/"+run_name(commit)

def authorize(env):
    commit=env.get("MOSA_PNE_EXPECTED_COMMIT","")
    if (not re.fullmatch(r"[0-9a-f]{40}",commit) or
        env.get("MOSA_PNE_AUTHORIZATION")!=TOKEN+commit or
        env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_RUN_ATTEMPT")!="1" or
        env.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or env.get("GITHUB_REF")!="refs/heads/main" or
        env.get("GITHUB_REPOSITORY")!="masterxfix/MOSA-2" or env.get("GITHUB_SHA")!=commit):
        raise PermissionError("EXACT_ONE_PNE_MANUAL_AUTHORIZATION_REQUIRED")
    return commit

def php_source(project=ROOT,release_root=RELEASE,run_root=RUN,entry=True):
    source=(project/"scripts/market_collector/actions_acceptance.php").read_text()
    # The existing generic manifest function is reused verbatim; no onboarding path.
    manifest=source[source.index("function manifest("):source.index("function privateItem(")]
    header="""<?php
declare(strict_types=1);
namespace Mosa2\\MarketAcceptance;
use function Mosa2\\Phase2\\{check,same};
use function Mosa2\\MarketLive\\completePlan;
use function Mosa2\\MarketIdentity\\{planAssetIdentity,planMarketRoute};
"""
    body=(project/"scripts/market_collector/dogado_pne_live.php").read_text()
    expected="<?php\ndeclare(strict_types=1);\n"
    if not body.startswith(expected):raise ValueError("LAUNCHER_SOURCE_FORMAT")
    body=body[len(expected):].replace("@RELEASE@",release_root).replace("@RUN@",run_root)
    code=header+manifest+"\n"+body
    if entry:code+="\n\\Mosa2\\DogadoPne\\main();\n"
    return code[len("<?php\n"):]

def remote_source():
    common=directories.REMOTE_SOURCE.split('if __name__=="__main__":')[0]
    probe=(ROOT/"scripts/collector_remote_offline_probe.py").read_text()
    function=next(n for n in ast.parse(probe).body if isinstance(n,ast.FunctionDef) and n.name=="integrity")
    integrity=ast.get_source_segment(probe,function)
    body=(ROOT/"scripts/collector_dogado_pne_remote.py").read_text()
    return common+"\n"+integrity+"\n"+body

def package():
    archive,manifest=release.build(ROOT,RELEASE_COMMIT)
    meta=release.verify(ROOT,RELEASE_COMMIT,archive,manifest)
    if hashlib.sha256(archive).hexdigest()!=private.ARCHIVE_SHA256 or len(meta["files"])!=33 or meta["payload_bytes"]!=248105:
        raise ValueError("QUALIFIED_RELEASE_CHANGED")
    return meta

def actions_timing(env):
    result=dict(driver_started_utc=datetime.now(timezone.utc).isoformat())
    run=env.get("GITHUB_RUN_ID","")
    if not re.fullmatch(r"[1-9][0-9]{0,19}",run):return result
    try:
        request=urllib.request.Request("https://api.github.com/repos/masterxfix/MOSA-2/actions/runs/"+run,
                                      headers={"Accept":"application/vnd.github+json","User-Agent":"MOSA-2-once"})
        with urllib.request.urlopen(request,timeout=5) as reply:data=json.loads(reply.read(65537))
        created=datetime.fromisoformat(data["created_at"].replace("Z","+00:00"))
        started=datetime.fromisoformat(data["run_started_at"].replace("Z","+00:00"))
        now=datetime.fromisoformat(result["driver_started_utc"])
        result.update(queue_ms=(started-created).total_seconds()*1000,
                      actions_before_driver_ms=(now-started).total_seconds()*1000)
    except Exception:result["startup_api"]="UNAVAILABLE"
    return result

def execute(env,paramiko):
    commit=authorize(env)
    if release.git(ROOT,"rev-parse","HEAD").decode().strip()!=commit:raise PermissionError("CHECKOUT_BINDING")
    if release.git(ROOT,"ls-remote","origin","refs/heads/main").decode().split()[0]!=commit:
        raise PermissionError("MAIN_BINDING")
    config=shared.configuration(env)
    manifest=package();run=run_directory(commit);php=php_source(run_root=run)
    data=dict(commit=commit,authorization=TOKEN+commit,isin="DE000A0JBPG2",release_commit=RELEASE_COMMIT,
              password=env["MOSA_TEST_DB_PASSWORD"],manifest=manifest,php_source=php,
              php_sha256=hashlib.sha256(php.encode()).hexdigest())
    report=dict(ok=False,status="FAILED",stage="ssh",asset="PNE AG",isin="DE000A0JBPG2",
                commit=commit,release=RELEASE,run=run,provider_requests=0,automatic_retries=0,
                github=actions_timing(env))
    logging.getLogger("paramiko").disabled=True
    from scripts.collector_dogado_pne_diagnose import fingerprint
    dispatched=False;clock=time.perf_counter()
    try:
        status={}
        with shared.ssh_client(config,status,paramiko) as transport:
            report["ssh"]=status;report["ssh_ms"]=(time.perf_counter()-clock)*1000
            t=time.perf_counter()
            with paramiko.SFTPClient.from_transport(transport) as sftp:
                sftp.get_channel().settimeout(12)
                report["release_before"]=private.readback(sftp,RELEASE,manifest)
                report["previous_run_before"]=fingerprint(sftp)
            report["sftp_before_ms"]=(time.perf_counter()-t)*1000
            report["stage"]="remote_attempt"
            print(json.dumps(dict(event="remote_attempt_start",commit=commit,isin="DE000A0JBPG2")),flush=True)
            command=shlex.join(["/opt/alt/python311/bin/python3.11","-I","-B","-c",remote_source()])
            dispatched=True
            code,out,errors,elapsed=remote.remote_call(transport,command,
                json.dumps(data,separators=(",",":")).encode(),timeout=145)
            report["remote_supervisor_ms"]=elapsed
            if code or errors:raise RuntimeError("REMOTE_RECEIPT_UNAVAILABLE")
            result=json.loads(out);report["collector"]=result
            if result.get("status") not in ("COMPLETE","FAILED","OUTCOME_UNKNOWN"):raise ValueError("OUTCOME_STATUS")
            report.update(ok=result.get("ok") is True,status=result["status"],provider_requests=result.get("provider_requests"))
            t=time.perf_counter()
            with paramiko.SFTPClient.from_transport(transport) as sftp:
                sftp.get_channel().settimeout(12)
                report["release_after"]=private.readback(sftp,RELEASE,manifest)
                report["previous_run_after"]=fingerprint(sftp)
                if report["previous_run_before"]!=report["previous_run_after"]:raise RuntimeError("PREVIOUS_RUN_CHANGED")
                report["previous_run_unchanged"]="PASS"
            report["sftp_after_ms"]=(time.perf_counter()-t)*1000
            if report["ok"]:
                report["historical_comparison"]=dict(historical_collector_ms=37600,
                    local_runtime_ms=result["collector_ms"],
                    local_with_preflight_ms=result["total_with_preflight_ms"],
                    runtime_reduction_percent=round((1-result["collector_ms"]/37600)*100,2),
                    caveat="Different acquisition time; additional exhaustive integrity checkpoints; excludes Actions/SSH/SFTP")
            report["supervisor_overhead_ms"]=max(0,elapsed-result.get("total_with_preflight_ms",0))
            report["stage"]="finished"
    except Exception as error:
        report.update(ok=False,failure_type=type(error).__name__,
                      failure_code="REMOTE_OUTCOME_UNAVAILABLE" if dispatched else "START_PREREQUISITE_FAILED",
                      failure_phase=report["stage"],commit_state="unbekannt" if dispatched else "nicht bestätigt")
        if dispatched:
            report["status"]="OUTCOME_UNKNOWN"
            if "collector" not in report:report["provider_requests"]="UNKNOWN_MAX_1"
    report["driver_total_ms"]=(time.perf_counter()-clock)*1000
    report["secrets_in_log"]="NEIN/PASS"
    return report

def main():
    import paramiko
    try:report=execute(os.environ,paramiko)
    except Exception as error:report=dict(ok=False,status="FAILED",stage="authorization",failure_code="START_AUTHORIZATION_OR_CONFIGURATION_FAILED",
        failure_phase="authorization",php_process_started=False,php_exitcode=None,provider_started=False,commit_state="nicht bestätigt",provider_requests=0)
    encoded=shared.public_text(report,os.environ)
    print(encoded,flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as summary:
            summary.write("One-PNE Dogado collector live receipt\n\n~~~json\n"+encoded+"\n~~~\n")
    return 0 if report["ok"] and json.loads(encoded).get("ok") else 1

if __name__=="__main__":raise SystemExit(main())
