"""Offline Phase 1B guards and PHP syntax; no DB connection or hosting access."""

from pathlib import Path
import json
import subprocess
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "phase1b"


class Phase1BTests(unittest.TestCase):
    def test_php_sources_parse(self):
        for path in sorted(SOURCE.glob("*.php")):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["php", "-l", str(path)], capture_output=True, text=True, timeout=15
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_target_runtime_identifier_and_row_budget_guards(self):
        result = subprocess.run(
            ["php", str(SOURCE / "self_test.php")],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["offline_guard_rejections"], 17)
        self.assertEqual(report["database_connections"], 0)
