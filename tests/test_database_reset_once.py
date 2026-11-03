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
        self.assertIn("const TABLES = [", PHP)
        self.assertEqual(len(re.findall(r"'m2_[a-z_]+',?", PHP.split("const TABLES = [", 1)[1].split("];", 1)[0])), 17)

    def test_reset_uses_delete_order_without_schema_or_fk_shortcuts(self):
        self.assertIn("$db->exec('DELETE FROM '.qi($table));", PHP)
        self.assertNotIn("TRUNCATE", PHP.upper())
        self.assertNotIn("DROP TABLE", PHP.upper())
        self.assertNotIn("FOREIGN_KEY_CHECKS=0", PHP.upper())
        self.assertIn("same((int)$db->query('SELECT @@foreign_key_checks')->fetchColumn(), 1", PHP)

    def test_baseline_and_independent_postcheck_are_required(self):
        self.assertIn("baseline($db)", PHP)
        self.assertIn("postcheck($db, $root", PHP)
        self.assertIn("connection($password); readOnlyBegin($db)", PHP)
        self.assertIn("collector_disabled", PHP)


if __name__ == "__main__":
    unittest.main()

