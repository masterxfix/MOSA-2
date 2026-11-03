import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PHP = (ROOT / "scripts/database_reset_once.php").read_text(encoding="utf-8")
REMOTE = (ROOT / "scripts/database_reset_once_remote.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/database-reset-once.yml").read_text(encoding="utf-8")


class DatabaseResetContractTests(unittest.TestCase):
    def test_reset_is_commit_bound_and_first_attempt_only(self):
        self.assertIn("first_attempt_only", PHP)
        self.assertIn("MOSA2-TEST-DATA-RESET:", PHP)
        self.assertIn("GITHUB_RUN_ATTEMPT", REMOTE)
        self.assertIn("test \"$RESET_AUTHORIZATION\" = \"MOSA2-TEST-DATA-RESET:$GITHUB_SHA\"", WORKFLOW)

    def test_only_target_database_and_expected_schema_are_allowed(self):
        self.assertIn("TARGET_DATABASE = 'h29077_mosa2_test'", PHP)
        self.assertIn("EXPECTED_VERSION = '8.0.26-16'", PHP)
        self.assertIn("envelope(6)['tables']", PHP)
        self.assertIn("CollectorSchema6\\schemas()", PHP)
        self.assertIn("'schema_version' => 6", PHP)
        self.assertIn("same(count($actual), 6, 'ledger_count')", PHP)

    def test_reset_uses_delete_order_without_schema_or_fk_shortcuts(self):
        self.assertIn("$db->exec('DELETE FROM '.qi($table).$filter);", PHP)
        self.assertIn("job_key <> 'collector_reservations_v1'", PHP)
        self.assertIn("'m2_fundamental_current', 'm2_fundamental_observations', 'm2_provider_fetches'", PHP)
        self.assertIn("'m2_collector_requests', 'm2_collector_cycles', 'm2_collector_days'", PHP)
        self.assertNotIn("TRUNCATE", PHP.upper())
        self.assertNotIn("DROP TABLE", PHP.upper())
        self.assertNotIn("FOREIGN_KEY_CHECKS=0", PHP.upper())
        self.assertIn("same((int)$db->query('SELECT @@foreign_key_checks')->fetchColumn(), 1", PHP)

    def test_dynamic_ssh_tunnel_port_reaches_all_database_connections(self):
        self.assertIn('"db_port": port', REMOTE)
        self.assertIn("check(is_int($port) && $port >= 1 && $port <= 65535", PHP)
        self.assertEqual(PHP.count("connection($password, '127.0.0.1', $port)"), 3)
        self.assertNotIn("connection($password);", PHP)

    def test_commit_outcome_is_not_reported_as_not_executed(self):
        self.assertIn("$phase = 'COMMIT';", PHP)
        self.assertIn("$commitAttempted = true; $db->commit(); $committed = true;", PHP)
        self.assertIn("'RESET_POSTCHECK_FAILED'", PHP)
        self.assertIn("'RESET_OUTCOME_UNKNOWN'", PHP)
        self.assertIn('"SUBPROCESS_TIMEOUT"', REMOTE)
        self.assertIn("return result", REMOTE)
        self.assertIn("'error_code' => safeFailureCode($error)", PHP)

    def test_schema6_retains_definitions_and_bootstrap(self):
        self.assertIn("'m2_fundamental_metrics', 'm2_fundamental_units', 'm2_collector_state'", PHP)
        self.assertIn("lockedDatabase($db)", PHP)
        self.assertIn("serialize($rows)", PHP)
        self.assertNotIn("const TABLES = [", PHP)

    def test_baseline_and_independent_postcheck_are_required(self):
        self.assertIn("baseline($db)", PHP)
        self.assertIn("postcheck($db, $root", PHP)
        self.assertIn("connection($password, '127.0.0.1', $port); readOnlyBegin($db)", PHP)
        self.assertIn("collector_disabled", PHP)


if __name__ == "__main__":
    unittest.main()

