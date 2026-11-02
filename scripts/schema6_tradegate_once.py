"""Single PNE Tradegate execution using the existing pinned SSH/tunnel boundary."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collector_actions as shared

AUTHORIZATION_PREFIX = "MOSA2-PNE-TRADEGATE-ONE-SHOT-20261102:"


def authorize(env):
    commit = env.get("MOSA_PNE_EXPECTED_COMMIT", "")
    if (not re.fullmatch(r"[0-9a-f]{40}", commit)
            or env.get("MOSA_PNE_AUTHORIZATION") != AUTHORIZATION_PREFIX + commit
            or env.get("GITHUB_ACTIONS") != "true"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_REPOSITORY") != "masterxfix/MOSA-2"
            or env.get("GITHUB_SHA") != commit):
        raise PermissionError("EXACT_PNE_TRADEGATE_ONE_SHOT_AUTHORIZATION_REQUIRED")
    return commit


def invoke_once(port, private, env, *, run=subprocess.run):
    commit = authorize(env)
    config = dict(python=sys.executable, php="php", project=str(ROOT), runtime_path=env.get("PATH", ""),
                  public_root=str(ROOT), db_host="127.0.0.1", db_port=port,
                  state_contract=dict(schema_version=6, allow_current=True), verification_mode="proof",
                  allow_duplicate=True, one_shot_scope="PNE_TRADEGATE",
                  one_shot_authorization=env["MOSA_PNE_AUTHORIZATION"])
    wire = dict(scope="pne_tradegate", commit=commit, authorization=env["MOSA_PNE_AUTHORIZATION"],
                password=env["MOSA_TEST_DB_PASSWORD"], private_root=private, config=config)
    child_env = {k: env[k] for k in ("PATH", "HOME", "LANG", "SYSTEMROOT", "TEMP", "TMP") if k in env}
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    reply = run(["php", str(ROOT / "scripts/market_collector/schema6_tradegate_once.php")],
                input=json.dumps(wire), text=True, capture_output=True, cwd=ROOT, env=child_env, timeout=480)
    if reply.returncode != 0 or reply.stderr:
        raise RuntimeError("COLLECTOR_PROCESS_FAILED")
    result = json.loads(reply.stdout)
    if not isinstance(result, dict) or type(result.get("ok")) is not bool:
        raise RuntimeError("COLLECTOR_RESULT_INVALID")
    return result


def execute(env, paramiko=None):
    report = dict(ok=False, stage="configuration", ssh="NOT_CHECKED", host_key="NOT_CHECKED",
                  db_tunnel="NOT_CHECKED", acceptance=None, provider_gets=0)
    try:
        config = shared.configuration(env)
        authorize(env)
        if paramiko is None:
            import paramiko
        report["stage"] = "ssh"
        with shared.ssh_client(config, report, paramiko) as transport:
            report["stage"] = "db_tunnel"
            with shared.tunnel(transport, report) as port:
                report["stage"] = "acceptance"
                import tempfile
                with tempfile.TemporaryDirectory(prefix="mosa2-pne-tradegate-") as private:
                    os.chmod(private, 0o700)
                    report["acceptance"] = invoke_once(port, private, env)
                    report["ok"] = report["acceptance"]["ok"]
                    report["provider_gets"] = report["acceptance"].get("provider_gets", 0)
        report["stage"] = "finished"
    except shared.ConfigurationError as error:
        report["failure"] = str(error)
    except PermissionError as error:
        report["failure"] = str(error)
    except Exception as error:
        report["failure_type"] = type(error).__name__
        if report["stage"] in ("ssh", "db_tunnel"):
            report[report["stage"]] = "FAIL"
    return report


def main():
    result = execute(os.environ)
    encoded = json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2)
    print(encoded)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write("MOSA-2 PNE Tradegate one-shot\n\n" + encoded + "\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
