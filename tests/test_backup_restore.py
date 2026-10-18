"""Offline backup/restore safety and serialization tests."""
import json
from pathlib import Path
import subprocess
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "phase1g"


class BackupRestoreTests(unittest.TestCase):
    def test_php_sources_parse(self):
        for path in sorted(SOURCE.glob("*.php")):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["php", "-l", str(path)], capture_output=True, text=True, timeout=15
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_target_isolation_serialization_and_corruption_guards(self):
        result = subprocess.run(
            ["php", str(SOURCE / "self_test.php")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["backup_checks"], 25)
        self.assertEqual(report["database_connections"], 0)
