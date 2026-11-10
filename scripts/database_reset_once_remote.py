"""One bounded, commit-bound reset over the existing pinned SSH/tunnel."""
import json
import logging
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collector_actions as access
import collector_db_locality as remote
from issue61_inventory import HOST_INVENTORY


def execute(env, paramiko=None):
    if env.get("GITHUB_RUN_ATTEMPT") != "1":
        return {"status": "FIRST_ATTEMPT_ONLY"}
    if env.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        return {"status": "WORKFLOW_DISPATCH_ONLY"}
    if (env.get("GITHUB_REPOSITORY") != "masterxfix/MOSA-2" or env.get("GITHUB_ACTOR") != "masterxfix"
            or env.get("GITHUB_REF") != "refs/heads/codex/issue-61-controlled-reset"):
        return {"status": "ISSUE61_SCOPE_ONLY"}
    commit = env.get("MOSA2_RESET_EXPECTED_COMMIT", "")
    if not re.fullmatch(r"[0-9a-f]{40}",commit) or env.get("GITHUB_SHA") != commit:
        return {"status": "COMMIT_BINDING_REJECTED"}
    authorization = env.get("MOSA2_RESET_AUTHORIZATION", "")
    if authorization != "MOSA2-ISSUE61-CONTENT-RESET:" + commit:
        return {"status": "AUTHORIZATION_REJECTED"}

    stage = "CONFIGURATION"
    try:
        config = access.configuration(env)
        if paramiko is None:
            import paramiko
        logging.getLogger("paramiko").disabled = True
        logging.getLogger("paramiko").addHandler(logging.NullHandler())
        logging.getLogger("paramiko").propagate = False
        stage = "SSH"
        with access.ssh_client(config, {}, paramiko) as transport:
            stage = "KNOWN_WRITERS"
            cmd=shlex.join(["/opt/alt/python311/bin/python3.11","-I","-B","-c",HOST_INVENTORY])
            rc,data,errors,_=remote.remote_call(transport,cmd,timeout=35)
            if rc or errors:
                return {"status":"RESET_NOT_EXECUTED","phase":"KNOWN_WRITERS","error_code":"subscription_inventory_rejected"}
            inventory=json.loads(data)
            for key in ("cron","user_processes","system_unit_files","user_unit_files","user_timers","system_timers"):
                if inventory[key].get("matches",0):
                    return {"status":"RESET_NOT_EXECUTED","phase":"KNOWN_WRITERS","error_code":"m2_writer_detected:"+key}
            if not all(inventory[k].get("visible") for k in ("cron","user_processes")):
                return {"status":"RESET_NOT_EXECUTED","phase":"KNOWN_WRITERS","error_code":"m2_subscription_process_list_unavailable"}
            stage = "TUNNEL"
            with access.tunnel(transport, {}) as port:
                request = {
                    "password": env["MOSA_TEST_DB_PASSWORD"],
                    "attempt": env["GITHUB_RUN_ATTEMPT"],
                    "commit": commit,
                    "authorization": authorization,
                    "mode": "issue61-schema6-content-reset",
                    "db_port": port,
                }
                child_env = {k: env[k] for k in ("PATH", "HOME", "LANG", "SYSTEMROOT", "TEMP", "TMP") if k in env}
                child_env["PYTHONDONTWRITEBYTECODE"] = "1"
                stage = "SUBPROCESS"
                reply = subprocess.run(
                    ["php", str(ROOT / "scripts/database_reset_once.php")],
                    input=json.dumps(request), text=True, capture_output=True,
                    cwd=ROOT, env=child_env, timeout=600,
                )
                if reply.stderr or len(reply.stdout) > 32768:
                    return {"status": "RESET_OUTCOME_UNKNOWN", "phase": "SUBPROCESS_OUTPUT_REJECTED"}
                result = json.loads(reply.stdout)
                allowed = {"RESET_SUCCEEDED", "RESET_NOT_EXECUTED", "RESET_OUTCOME_UNKNOWN", "RESET_POSTCHECK_FAILED"}
                if not isinstance(result, dict) or result.get("status") not in allowed:
                    return {"status": "RESET_OUTCOME_UNKNOWN", "phase": "SUBPROCESS_RESULT_REJECTED"}
                if (reply.returncode == 0) != (result["status"] == "RESET_SUCCEEDED"):
                    return {"status": "RESET_OUTCOME_UNKNOWN", "phase": "SUBPROCESS_EXIT_MISMATCH"}
                result["known_m2_subscription_writers"]=0
                return result
    except subprocess.TimeoutExpired:
        return {"status": "RESET_OUTCOME_UNKNOWN", "phase": "SUBPROCESS_TIMEOUT"}
    except Exception:
        return {"status": "RESET_OUTCOME_UNKNOWN" if stage=="SUBPROCESS" else "RESET_NOT_EXECUTED", "phase":stage,
                "error_code":"remote_step_failed"}


def public_text(report, env):
    encoded = json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2)
    for name in ("MOSA_TEST_SFTP_PASSWORD", "MOSA_TEST_SFTP_HOST_KEY_SHA256", "MOSA_TEST_DB_PASSWORD"):
        value = env.get(name)
        if value and (value in encoded or json.dumps(value)[1:-1] in encoded):
            return json.dumps({"status": "SECRET_OUTPUT_BLOCKED"})
    return encoded


if __name__ == "__main__":
    import paramiko
    report = execute(os.environ, paramiko)
    print(public_text(report, os.environ))
    sys.exit(0 if report.get("status") == "RESET_SUCCEEDED" else 1)

