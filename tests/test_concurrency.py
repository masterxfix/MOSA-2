"""Offline guards for bounded concurrent transaction scenarios."""
import json
from pathlib import Path
import subprocess
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "phase1f"


class ConcurrencyTests(unittest.TestCase):
    def test_php_concurrency_sources_parse(self):
        for path in sorted(SOURCE.glob("*.php")):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["php", "-l", str(path)], capture_output=True, text=True, timeout=15
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_scenario_limits_lock_classification_and_shared_read_guards(self):
        result = subprocess.run(
            ["php", str(SOURCE / "self_test.php")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["concurrency_checks"], 40)
        self.assertEqual(report["connections_limit"], 4)
        self.assertLessEqual(report["normal_repetitions"] * 2, 10)
        self.assertLessEqual(report["conflicts_per_runtime"] * 2, 3)
        self.assertLessEqual(report["read_samples"], 10)
        self.assertEqual(report["database_connections"], 0)
