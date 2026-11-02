import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FundamentalsWebTests(unittest.TestCase):
    def php_executable(self):
        candidates = [shutil.which('php')]
        if os.name == 'nt':
            candidates.append(r'C:\php\php.exe')
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return str(candidate)
        self.fail('PHP executable not found')

    def test_reader_and_endpoint_are_get_only_and_bounded(self):
        reader = (ROOT / 'api/fundamentals_read.php').read_text(encoding='utf-8')
        endpoint = (ROOT / 'api/fundamentals.php').read_text(encoding='utf-8')
        combined = reader + endpoint
        self.assertIn('SET SESSION TRANSACTION READ ONLY', reader)
        self.assertIn('WHERE o.asset_id IN (', reader)
        self.assertIn('LIMIT 2304', reader)
        self.assertIn("($_SERVER['REQUEST_METHOD']??'GET')!=='GET'", endpoint)
        for forbidden in ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'ALTER TABLE', 'CREATE TABLE', 'MOSA_TEST_DB_PASSWORD', 'evidence_json'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)
        for file in ('api/fundamentals.php', 'api/fundamentals_read.php'):
            result = subprocess.run([self.php_executable(), '-l', file], cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_real_renderer_maps_current_and_historical_values_without_conversion(self):
        result = subprocess.run(['node', str(ROOT / 'tests/fixtures/fundamentals_dom_runtime.js'),
                                 str(ROOT / 'assets/js/fundamentals.js'), 'stored'],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data['total'], '02')
        self.assertEqual(data['assets'], ['BYD', 'Ubtech Robotics'])
        self.assertIn('803964958', data['byd'])
        self.assertIn('777102455', data['byd'])
        self.assertIn('CNY_THOUSAND', data['byd'])
        self.assertIn('2000999', data['ubtech'])
        self.assertIn('1305361', data['ubtech'])
        self.assertTrue(any('Current' in value for value in data['byd']))

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_renderer_fails_closed_without_database_data(self):
        result = subprocess.run(['node', str(ROOT / 'tests/fixtures/fundamentals_dom_runtime.js'),
                                 str(ROOT / 'assets/js/fundamentals.js'), 'error'],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data['error'], 'Fundamentaldaten nicht verfügbar')
        self.assertNotIn('password', result.stdout.lower())

    def test_page_and_navigation_expose_the_new_view_without_private_details(self):
        page = (ROOT / 'fundamentaldaten.html').read_text(encoding='utf-8')
        navigation = (ROOT / 'assets/js/navigation.js').read_text(encoding='utf-8')
        homepage = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('data-fundamentals-view', page)
        self.assertIn('fundamentaldaten.html', navigation)
        self.assertIn('Fundamentaldaten entdecken', homepage)
        self.assertNotRegex(page + navigation + homepage, r'password|secret|token|m2_entities|configcenter|/var/')


if __name__ == '__main__':
    unittest.main()
