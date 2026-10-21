"""One bounded SSH module test against the immutable installed release; no deployment."""
import base64
from dataclasses import asdict
import hashlib
import json
import logging
import os
from pathlib import Path
import shlex
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from scripts import collector_release as release
from scripts import deploy_private_collector as private
from scripts import collector_remote_offline_probe as probe
import collector_actions as shared
import collector_db_locality as remote
import deploy_test_sftp as profile

def cases():
    # Reuse the same synthetic fixtures and contracts as the existing references.
    sys.path.insert(0,str(ROOT/"tests"))
    import test_market_collector_v1 as fixtures
    frankfurt=fixtures.FrankfurtCollectorTests();frankfurt.setUp()
    yahoo=fixtures.MarketCollectorTests();yahoo.setUp()
    result=[]
    for module,adapter,request,route,response,created in (
        ("scripts.market_collector.boerse_frankfurt","FrankfurtSnapshotV1",frankfurt.request,
         frankfurt.route,frankfurt.response,frankfurt.created),
        ("scripts.market_collector.yahoo_chart","YahooChartSnapshotV1",
         *yahoo.inputs("GBX"),yahoo.created)):
        result.append(dict(module=module,adapter=adapter,request=asdict(request),
            route=dict(route.route),payload=base64.b64encode(response.payload_bytes).decode(),
            collected_at=response.collected_at,created_at=created))
    return result

def request():
    archive,manifest=release.build(ROOT,probe.RELEASE_COMMIT)
    metadata=release.verify(ROOT,probe.RELEASE_COMMIT,archive,manifest)
    if hashlib.sha256(archive).hexdigest()!=private.ARCHIVE_SHA256:
        raise ValueError("QUALIFIED_PACKAGE_CHANGED")
    data=cases()
    probe.PHP_BINARY=shutil.which("php")
    if not probe.PHP_BINARY:raise ValueError("REFERENCE_PHP_MISSING")
    original=probe.subprocess.run
    probe.subprocess.run=probe.pinned_run
    try:expected=probe.evaluate(ROOT,data)
    finally:probe.subprocess.run=original
    return dict(root=probe.RELEASE,manifest=metadata,cases=data,expected=expected)

def command():
    source=(ROOT/"scripts/collector_remote_offline_probe.py").read_text()
    return shlex.join([probe.PYTHON,"-I","-B","-c",source])

def execute(env,paramiko):
    if env.get("GITHUB_RUN_ATTEMPT")!="1":
        raise PermissionError("FIRST_ATTEMPT_ONLY")
    data=request()
    wire=json.dumps(data,separators=(",",":")).encode()
    if len(wire)>60000:raise ValueError("INPUT_LIMIT")
    logging.getLogger("paramiko").disabled=True
    status={}
    with shared.ssh_client(profile.configuration(env),status,paramiko) as transport:
        with paramiko.SFTPClient.from_transport(transport) as sftp:
            sftp.get_channel().settimeout(12)
            readback=private.readback(sftp,probe.RELEASE,data["manifest"])
        # Exactly one fileless test execution; no retry and no tunnel.
        code,out,errors,elapsed=remote.remote_call(transport,command(),wire,timeout=65)
    if code or errors:raise ValueError("REMOTE_TEST_PROCESS_FAILED")
    result=json.loads(out)
    result.update(connection=status,independent_release_readback=readback,elapsed_ms=round(elapsed,3))
    if result.get("ok") is not True:return result
    if result.get("cases")!=data["expected"]:raise ValueError("INDEPENDENT_REFERENCE_COMPARISON")
    return result

def main():
    import paramiko
    try:result=execute(os.environ,paramiko)
    except Exception as error:
        result=dict(ok=False,failure_type=type(error).__name__,failure=str(error)[:160])
    text=shared.public_text(result,os.environ)
    print(text,flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as summary:
            summary.write("Installed release: synthetic in-memory offline test\n\n~~~json\n"+text+"\n~~~\n")
    return 0 if result["ok"] and json.loads(text).get("ok") else 1

if __name__=="__main__":
    raise SystemExit(main())
