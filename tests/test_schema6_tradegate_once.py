"""Offline safety checks for the isolated PNE schema-6 one-shot entrypoint."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("schema6_tradegate_once", ROOT / "scripts/schema6_tradegate_once.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def env():
    import collector_actions
    return {
        **{collector_actions.profile.PREFIX + key: value for key, value in collector_actions.profile.EXPECTED.items()},
        "MOSA_TEST_SFTP_PASSWORD": "synthetic-ssh-value",
        "MOSA_TEST_SFTP_HOST_KEY_SHA256": "SHA256:" + "A" * 43,
        "MOSA_TEST_DB_PASSWORD": "synthetic-db-value",
        "MOSA_PNE_EXPECTED_COMMIT": "a" * 40,
        "MOSA_PNE_AUTHORIZATION": module.AUTHORIZATION_PREFIX + "a" * 40,
        "GITHUB_ACTIONS": "true",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "masterxfix/MOSA-2",
        "GITHUB_SHA": "a" * 40,
        "PATH": "synthetic-path",
    }


class OneShotAuthTests(unittest.TestCase):
    def test_exact_context_and_authorization_are_required(self):
        self.assertEqual(module.authorize(env()), "a" * 40)
        for key in ("GITHUB_RUN_ATTEMPT", "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_REPOSITORY", "GITHUB_SHA",
                    "MOSA_PNE_EXPECTED_COMMIT", "MOSA_PNE_AUTHORIZATION"):
            invalid = env()
            invalid[key] = "invalid"
            with self.assertRaises(PermissionError):
                module.authorize(invalid)

    def test_php_child_receives_password_only_on_stdin_and_no_secret_environment(self):
        calls = []
        result = {"ok": True, "provider_gets": 1}
        reply = MagicMock(returncode=0, stderr="", stdout=json.dumps(result))

        def run(args, **kwargs):
            calls.append((args, kwargs))
            return reply

        module.invoke_once(45678, "/synthetic/private", env(), run=run)
        args, kwargs = calls[0]
        self.assertEqual(args[0], "php")
        self.assertEqual(json.loads(kwargs["input"])["password"], "synthetic-db-value")
        for key in ("MOSA_TEST_SFTP_PASSWORD", "MOSA_TEST_SFTP_HOST_KEY_SHA256", "MOSA_TEST_DB_PASSWORD"):
            self.assertNotIn(key, kwargs["env"])
        self.assertNotIn("synthetic-db-value", repr(args))

    def test_entrypoint_preserves_normal_schema6_stop_gate_and_is_manual_only(self):
        persistence = (ROOT / "scripts/market_collector/live_persistence.php").read_text(encoding="utf-8")
        self.assertIn("if($acquisitionGate===null)", persistence)
        self.assertIn("acquisitionAllowed($config['state_contract']??[])", persistence)
        workflow = (ROOT / ".github/workflows/market-tradegate-pne-once.yml").read_text(encoding="utf-8")
        self.assertNotIn("  push:", workflow)
        self.assertNotIn("  schedule:", workflow)
        self.assertIn("github.run_attempt == 1", workflow)
        self.assertIn("ref: @@DOLLAR@@{{ github.sha }}".replace("@@DOLLAR@@", "$"), workflow)

    def test_php_entrypoint_is_syntactically_valid(self):
        php = shutil.which("php")
        self.assertIsNotNone(php)
        result = subprocess.run([php, "-l", str(ROOT / "scripts/market_collector/schema6_tradegate_once.php")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")

    def test_pne_entrypoint_resolves_the_shared_proof_function(self):
        php = shutil.which("php")
        self.assertIsNotNone(php)
        source = (ROOT / "scripts/market_collector/schema6_tradegate_once.php").read_text(encoding="utf-8")
        self.assertIn(r"\Mosa2\MarketLive\proofRun($private,$password,$config,$manifest,$gate);", source)
        self.assertNotIn(r"\Mosa2\MarketAcceptance\proofRun(", source)
        # Loading the actual PHP entrypoint is offline and must not start main().
        script = ("require $argv[1];"
                  "$fn = new ReflectionFunction('Mosa2\\\\MarketLive\\\\proofRun');"
                  "echo $fn->getNumberOfParameters() . ':' . $fn->getNumberOfRequiredParameters();")
        result = subprocess.run([php, "-r", script, str(ROOT / "scripts/market_collector/schema6_tradegate_once.php")],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, "5:4")

    def test_proof_uses_the_configured_tunnel_endpoint_for_both_connections(self):
        source = (ROOT / "scripts/market_collector/live_persistence.php").read_text(encoding="utf-8")
        proof = source[source.index("function proofRun"):source.index("require_once __DIR__.'/runtime_persistence.php'")]
        self.assertIn("$connect=static fn()=>connection($password,$config['db_host']??'127.0.0.1',$config['db_port']??3307);", proof)
        self.assertEqual(proof.count("$p=$connect();"), 1)
        self.assertEqual(proof.count("$read=$connect();"), 1)
        self.assertNotIn("connection($password);", proof)


if __name__ == "__main__":
    unittest.main()
