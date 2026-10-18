"""Run the very same fail-closed PHP CHECK parser used by the live postcheck."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/phase2/check_expression.php'


class CheckExpressionTests(unittest.TestCase):
    def compare(self, expected, actual, show='CREATE TABLE test', qualified=False):
        script = ('require $argv[1]; $v=json_decode(stream_get_contents(STDIN),true);'
                  'echo json_encode(\\Mosa2\\Phase2\\compareCheck("test","ck_test",$v[0],$v[1],$v[2],$v[3]),JSON_THROW_ON_ERROR);')
        result = subprocess.run(['php', '-r', script, str(MODULE)],
                                input=json.dumps([expected, actual, show, qualified]), text=True,
                                capture_output=True, check=True)
        return json.loads(result.stdout)

    def test_positive_renderings(self):
        base = "status IN ('active', 'inactive', 'archived')"
        for actual in [base, " status  IN ( 'active',\n'inactive', 'archived' ) ",
                       "`status` IN ('active','inactive','archived')",
                       '('+base+')', '((('+base+')))',
                       "((`status`) IN (('active'), ('inactive'), ('archived')))"]:
            with self.subTest(actual=actual):
                self.assertTrue(self.compare(base, actual)['equal'])

    def test_semantic_changes_rejected(self):
        pairs = [
            ("status IN ('active','inactive')", "status IN ('active','archived')"),
            ('attempt_no >= 1', 'attempt_no > 1'),
            ('attempt_no >= 1', 'attempt >= 1'),
            ("status IN ('active','inactive')", "status IN ('active')"),
            ('a = 1 AND b = 2', 'a = 1 OR b = 2'),
            ('a = 1 AND (b = 2 OR c = 3)', '(a = 1 AND b = 2) OR c = 3'),
            ('CHAR_LENGTH(TRIM(scope_key)) > 0', 'LENGTH(TRIM(scope_key)) > 0'),
            ("status IN ('active','inactive')", "status IN ('inactive','active')"),
            ('a IN (0,1)', 'a NOT IN (0,1)'),
            ('a >= 1', 'a >= 2'), ('a >= 1', 'A >= 1'),
            ("a = 'Active'", "a = 'active'"),
            ('a >= 1', 'a >= 1 /* ignored? */'),
            ('a >= 1', 'a >= 1 + 0'),
            ('a >= 1', 'a >= 1;'),
        ]
        for expected, actual in pairs:
            with self.subTest(actual=actual):
                result = self.compare(expected, actual)
                self.assertFalse(result['equal'])
                self.assertEqual(result['server_check_clause'], actual)
                self.assertEqual(result['expected'], expected)
                self.assertEqual(result['show_create_table'], 'CREATE TABLE test')
                self.assertTrue(result['decision'])

    def test_function_grouping(self):
        self.assertTrue(self.compare(
            "identifier_type <> 'ticker' OR CHAR_LENGTH(TRIM(scope_key)) > 0",
            "((`identifier_type` <> 'ticker') OR (char_length(trim(`scope_key`)) > 0))")['equal'])

    def test_unknown_charset_fails_closed(self):
        self.assertFalse(self.compare("a = 'x'", "a = _utf8mb4'x'")['equal'])

    def test_exact_saved_server_diagnostic(self):
        diagnostic = json.loads((ROOT / 'docs/database/PHASE2_CHECK_DIAGNOSTIC.json').read_text(encoding='utf-8'))['m2_entities'][0]
        show = diagnostic['show_create_table'].replace('ck_entities_status', 'ck_test')
        self.assertTrue(self.compare(diagnostic['expected'], diagnostic['server_check_clause'], show, True)['equal'])

    def test_all_phase2_php_sources_parse(self):
        for path in (ROOT / 'scripts/phase2').glob('*.php'):
            result = subprocess.run(['php', '-l', str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fk_probe_is_new_child_not_referenced_parent_update(self):
        source = (ROOT / 'scripts/phase2/postcheck.php').read_text(encoding='utf-8')
        self.assertIn("VALUES (999999,'fixture',1,$now)", source)
        self.assertNotIn('UPDATE m2_assets SET entity_id=999999', source)

    def test_wrong_errno_is_preserved_without_database_message(self):
        script = r'''
require $argv[1];
class RejectPDO extends PDO {
    public function __construct() {}
    public function exec(string $statement): int|false {
        $e = new PDOException('private server text must not escape');
        $e->errorInfo = ['23000', 1451, 'private details'];
        throw $e;
    }
}
$results=[];
try { \Mosa2\Phase2\reject(new RejectPDO(), 'test', 1452, 'foreign_key', $results); }
catch (RuntimeException $e) { echo json_encode([$e->getMessage(), $results]); }
'''
        result = subprocess.run(['php', '-r', script, str(ROOT / 'scripts/phase2/postcheck.php')],
                                capture_output=True, text=True, check=True)
        message, results = json.loads(result.stdout)
        self.assertEqual(message, 'wrong_rejection:foreign_key:expected=1452:actual=1451')
        self.assertEqual(results['foreign_key']['mysql_errno'], 1451)
        self.assertNotIn('private', result.stdout)

    def test_observed_mysql_rendering_requires_three_way_agreement(self):
        expected = "status IN ('active','inactive','archived')"
        raw = r"(`status` in (_utf8mb4\'active\',_utf8mb4\'inactive\',_utf8mb4\'archived\'))"
        show = " CONSTRAINT `ck_test` CHECK ((`status` in (_utf8mb4'active',_utf8mb4'inactive',_utf8mb4'archived')))"
        self.assertTrue(self.compare(expected, raw, show, True)['equal'])
        for changed_raw, changed_show in [
            (raw.replace('active', 'altered'), show),
            (raw, show.replace('active', 'altered')),
            (raw.replace('_utf8mb4', '_latin1'), show),
            (raw.replace('status', 'other'), show),
            (raw.replace(' in ', ' not in '), show),
            (raw.replace('active', "act\\ive"), show),
            (raw, 'CREATE TABLE test'),
        ]:
            with self.subTest(raw=changed_raw, show=changed_show):
                self.assertFalse(self.compare(expected, changed_raw, changed_show, True)['equal'])
        self.assertFalse(self.compare(expected, raw, show, False)['equal'])


if __name__ == '__main__':
    unittest.main()
