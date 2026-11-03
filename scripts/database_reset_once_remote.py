"""One bounded, commit-bound reset over the existing pinned SSH/tunnel."""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collector_actions as access


def execute(env, paramiko=None):
    if env.get("GITHUB_RUN_ATTEMPT") != "1":
        return {"status": "FIRST_ATTEMPT_ONLY"}
    if env.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        return {"status": "WORKFLOW_DISPATCH_ONLY"}
    if env.get("GITHUB_REF") != "refs/heads/main":
        return {"status": "MAIN_BRANCH_ONLY"}
    commit = env.get("MOSA2_RESET_EXPECTED_COMMIT", "")
    if env.get("GITHUB_SHA") != commit:
        return {"status": "COMMIT_BINDING_REJECTED"}
    authorization = env.get("MOSA2_RESET_AUTHORIZATION", "")
    if authorization != "MOSA2-TEST-DATA-RESET:" + commit:
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
            stage = "TUNNEL"
            with access.tunnel(transport, {}) as port:
                request = {
                    "password": env["MOSA_TEST_DB_PASSWORD"],
                    "attempt": env["GITHUB_RUN_ATTEMPT"],
                    "commit": commit,
                    "authorization": authorization,
                    "mode": "irreversible-full-test-data-reset",
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
                return result
    except subprocess.TimeoutExpired:
        return {"status": "RESET_OUTCOME_UNKNOWN", "phase": "SUBPROCESS_TIMEOUT"}
    except Exception:
        return {"status": {"CONFIGURATION": "RESET_CONFIGURATION_REJECTED", "SSH": "RESET_SSH_REJECTED", "TUNNEL": "RESET_TUNNEL_REJECTED", "SUBPROCESS": "RESET_SUBPROCESS_REJECTED"}.get(stage, "RESET_UNEXPECTED_REJECTED")}


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

