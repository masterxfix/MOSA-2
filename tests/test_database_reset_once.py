"""Issue 61's bounded reset contract; live access is never used here."""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import database_reset_once_remote as remote

PHP = (ROOT / "scripts/database_reset_once.php").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/database-reset-once.yml").read_text(encoding="utf-8")


class ResetContractTests(unittest.TestCase):
    def test_purge_covers_exact_schema_and_fk_order(self):
        migrations = sorted((ROOT / "docs/database/migrations").glob("000[1-6]_*.sql"))
        tables, edges = set(), set()
        for path in migrations:
            for statement in path.read_text(encoding="utf-8").split(";"):
                match = re.search(r"(CREATE|ALTER) TABLE (m2_[a-z0-9_]+)",statement)
                if not match:
                    continue
                child = match[2]
                if match[1] == "CREATE":
                    tables.add(child)
                for parent in re.findall(r"\bREFERENCES (m2_[a-z0-9_]+)",statement):
                    edges.add((child,parent))
        order = re.findall(r"'(m2_[a-z0-9_]+)'",PHP.split("const PURGE_ORDER = [",1)[1].split("];",1)[0])
        self.assertEqual(len(order),25)
        self.assertEqual(set(order),tables-{"m2_schema_migrations"})
        for child,parent in edges-{("m2_units","m2_units"),("m2_collector_state","m2_collector_cycles")}:
            self.assertLess(order.index(child),order.index(parent),(child,parent))

    def test_historical_authorization_and_wrong_scope_cannot_reach_credentials(self):
        sha = "a"*40
        valid = dict(GITHUB_RUN_ATTEMPT="1",GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_ACTOR="masterxfix",
                     GITHUB_REF="refs/heads/codex/issue-61-controlled-reset",GITHUB_REPOSITORY="masterxfix/MOSA-2",
                     MOSA2_RESET_EXPECTED_COMMIT=sha,GITHUB_SHA=sha,
                     MOSA2_RESET_AUTHORIZATION="MOSA2-ISSUE61-CONTENT-RESET:"+sha)
        for changes, want in [
            ({"GITHUB_RUN_ATTEMPT":"2"},"FIRST_ATTEMPT_ONLY"),
            ({"GITHUB_EVENT_NAME":"schedule"},"WORKFLOW_DISPATCH_ONLY"),
            ({"GITHUB_REF":"refs/heads/main"},"ISSUE61_SCOPE_ONLY"),
            ({"GITHUB_ACTOR":"different"},"ISSUE61_SCOPE_ONLY"),
            ({"GITHUB_SHA":"b"*40},"COMMIT_BINDING_REJECTED"),
            ({"MOSA2_RESET_AUTHORIZATION":"MOSA2-TEST-DATA-RESET:"+sha},"AUTHORIZATION_REJECTED"),
        ]:
            self.assertEqual(remote.execute(valid | changes)["status"],want)
        self.assertNotRegex(WORKFLOW,r"(?m)^\s*(schedule|push|workflow_run|pull_request):")

    def test_fk_hint_only_for_self_reference_and_no_ddl(self):
        self.assertEqual(re.findall(r"DELETE /\*\+ SET_VAR\(foreign_key_checks=OFF\) \*/ FROM (\w+)", PHP),["m2_units"])
        self.assertNotRegex(PHP,r"(?i)\b(?:TRUNCATE|DROP (?:TABLE|DATABASE)|ALTER TABLE|SET (?:SESSION )?foreign_key_checks)\b")


if __name__ == "__main__":
    unittest.main()
