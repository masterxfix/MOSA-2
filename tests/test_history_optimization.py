"""Offline guards for the bounded History optimization comparison."""
import json
from pathlib import Path
import subprocess
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "phase1e"


class HistoryOptimizationTests(unittest.TestCase):
    def test_php_optimization_sources_parse(self):
        for path in sorted(SOURCE.glob("*.php")):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["php", "-l", str(path)], capture_output=True, text=True, timeout=15
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_index_direction_stage_budget_and_plan_parser(self):
        result = subprocess.run(
            ["php", str(SOURCE / "self_test.php")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["optimization_checks"], 45)
        self.assertLessEqual(report["candidate_limit"], 3)
        self.assertEqual(report["database_connections"], 0)
