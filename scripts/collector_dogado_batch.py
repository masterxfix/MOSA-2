"""Prepared manual 1..10-equity start. Deliberately disabled pending separate live approval."""
import ast
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shlex
from scripts import collector_dogado_pne as existing
import collector_actions as shared
import collector_db_locality as remote

ROOT=Path(__file__).resolve().parents[1]
LIVE_ENABLED=False
TOKEN="MOSA2-DOGADO-BATCH:"

def scope(env):
    commit=env.get("MOSA_BATCH_EXPECTED_COMMIT","");label=env.get("MOSA_BATCH_RUN_ID","")
    if not re.fullmatch(r"[0-9a-f]{40}",commit) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}",label):
        raise PermissionError("BATCH_BINDING")
    values=json.loads(env.get("MOSA_BATCH_SELECTION","null"))
    if not isinstance(values,list) or not 1<=len(values)<=10 or any(not isinstance(v,str) or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]",v) for v in values) or len(set(values))!=len(values):
        raise PermissionError("BATCH_SELECTION")
    digest=hashlib.sha256(json.dumps(values,separators=(",",":")).encode()).hexdigest()
    expected=TOKEN+commit+":"+label+":"+digest
    if (env.get("MOSA_BATCH_AUTHORIZATION")!=expected or env.get("GITHUB_ACTIONS")!="true"
        or env.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or env.get("GITHUB_RUN_ATTEMPT")!="1"
        or env.get("GITHUB_REF")!="refs/heads/main" or env.get("GITHUB_SHA")!=commit
        or env.get("GITHUB_REPOSITORY")!="masterxfix/MOSA-2"):
        raise PermissionError("BATCH_BINDING")
    return commit,label,values,"batch-"+commit+"-"+label+"-"+digest[:16]

def remote_source():
    # Reuse the proven supervisor functions, never its PNE entry point or run_once.
    tree=ast.parse((ROOT/"scripts/collector_dogado_pne_remote.py").read_text())
    names={"guard","new_metadata","file_once","stop_group","safe_code","process_code","ChildStop","child"}
    assignments={"RELEASE_COMMIT","ROOT","RELEASE","PHP","PHP_FLAGS","INODES","SAFE_FAILURE_CODES"}
    nodes=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))
           or isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names
           or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in assignments for t in n.targets)]
    original=(ROOT/"scripts/collector_dogado_pne_remote.py").read_text()
    generic="\n".join(ast.get_source_segment(original,n) for n in nodes)
    common=existing.remote_source().split('"""One-shot process supervisor.')[0]
    return common+"\n"+generic+"\n"+(ROOT/"scripts/collector_dogado_batch_remote.py").read_text()

def execute(env,paramiko):
    if not LIVE_ENABLED:raise PermissionError("BATCH_LIVE_NOT_AUTHORIZED")
    commit,label,selection,name=scope(env)
    if existing.release.git(ROOT,"rev-parse","HEAD").decode().strip()!=commit:raise PermissionError("CHECKOUT_BINDING")
    if existing.release.git(ROOT,"ls-remote","origin","refs/heads/main").decode().split()[0]!=commit:raise PermissionError("MAIN_BINDING")
    config=shared.configuration(env);manifest=existing.package()
    run=existing.PRIVATE+"/runs/"+name
    php=existing.php_source(run_root=run,launcher="dogado_batch_live.php")
    data=dict(commit=commit,run_id=label,selection=selection,authorization=env["MOSA_BATCH_AUTHORIZATION"],
        release_commit=existing.RELEASE_COMMIT,manifest=manifest,password=env["MOSA_TEST_DB_PASSWORD"],
        php_source=php,php_sha256=hashlib.sha256(php.encode()).hexdigest())
    report=dict(ok=False,overall_status="FAILED_BEFORE_FIRST_COMMIT",commit=commit,run=run,
                github=existing.actions_timing(env),requested_count=len(selection),provider_requests=0,automatic_retries=0)
    import time
    started=time.perf_counter();dispatched=False
    logging.getLogger("paramiko").disabled=True
    try:
        with shared.ssh_client(config,report,paramiko) as transport:
            report["ssh_ms"]=(time.perf_counter()-started)*1000
            command=shlex.join(["/opt/alt/python311/bin/python3.11","-I","-B","-c",remote_source()])
            dispatched=True
            code,out,err,ms=remote.remote_call(transport,command,json.dumps(data,separators=(",",":")).encode(),timeout=120*len(selection)+30)
            report["remote_supervisor_ms"]=ms
            if code or err:raise RuntimeError("BATCH_RECEIPT_UNAVAILABLE")
            result=json.loads(out);report["batch"]=result
            report.update(ok=result.get("ok") is True,overall_status=result.get("overall_status","OUTCOME_UNKNOWN"),
                          provider_requests=result.get("provider_requests"))
            if type(result.get("local_batch_ms")) in (float,int):
                report["supervisor_overhead_ms"]=max(0,ms-result["local_batch_ms"])
    except Exception:
        report.update(ok=False,failure_code="BATCH_RECEIPT_UNAVAILABLE")
        if dispatched:report.update(overall_status="OUTCOME_UNKNOWN",provider_requests=None)
    report["driver_total_ms"]=(time.perf_counter()-started)*1000
    return report

def main():
    import paramiko
    try:r=execute(os.environ,paramiko)
    except Exception:r=dict(ok=False,overall_status="FAILED_BEFORE_FIRST_COMMIT",failure_code="BATCH_LIVE_NOT_AUTHORIZED_OR_INVALID_SCOPE",provider_requests=0)
    encoded=shared.public_text(r,os.environ);print(encoded,flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as f:f.write("Dogado batch receipt\n\n~~~json\n"+encoded+"\n~~~\n")
    return 0 if r.get("ok") and json.loads(encoded).get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
