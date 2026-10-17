"""Bounded 100000-row profile guards; no live database or hosting access."""

import json
from pathlib import Path
import subprocess
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "phase1d"


class History100000Tests(unittest.TestCase):
    def test_php_profile_sources_parse(self):
        for path in sorted(SOURCE.glob("*.php")):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["php", "-l", str(path)], capture_output=True, text=True, timeout=15
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_profile_separation_streaming_and_batch_statistics(self):
        result = subprocess.run(
            ["php", str(SOURCE / "self_test.php")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["profile_checks"], 250)
        self.assertEqual(report["history_rows"], 100000)
        self.assertEqual(report["history_batches"], 200)
        self.assertEqual(report["database_connections"], 0)
