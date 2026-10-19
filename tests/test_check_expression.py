"""Run the very same fail-closed PHP CHECK parser used by the live postcheck."""
import json
import itertools
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

    def test_associative_and_or_keeps_order_and_mixed_operator_grouping(self):
        for operator in ('AND', 'OR'):
            self.assertTrue(self.compare(f'a=1 {operator} (b=2 {operator} c=3)',
                                         f'((`a`=1 {operator.lower()} `b`=2) {operator.lower()} `c`=3)')['equal'])
            self.assertFalse(self.compare(f'a=1 {operator} b=2', f'b=2 {operator} a=1')['equal'])
        self.assertFalse(self.compare('a=1 AND (b=2 OR c=3)', '(a=1 AND b=2) OR c=3')['equal'])
        self.assertFalse(self.compare('a=1 OR (b=2 AND c=3)', '(a=1 OR b=2) AND c=3')['equal'])

    def test_associativity_has_independent_complete_three_valued_truth_table(self):
        def sql_and(a, b):
            return False if a is False or b is False else None if a is None or b is None else True
        def sql_or(a, b):
            return True if a is True or b is True else None if a is None or b is None else False
        for op in (sql_and, sql_or):
            for a, b, c in itertools.product((True, False, None), repeat=3):
                self.assertEqual(op(a, op(b, c)), op(op(a, b), c))

    def test_exact_mysql_volume_reassociation_and_semantic_mutations(self):
        expected = '(unit_contract_version IS NULL OR ((volume IS NULL AND volume_unit_key IS NULL AND volume_unit_version IS NULL) OR (volume IS NOT NULL AND volume_unit_key IS NOT NULL AND volume_unit_version IS NOT NULL))) IS TRUE'
        actual = '(((`unit_contract_version` is null) or ((`volume` is null) and (`volume_unit_key` is null) and (`volume_unit_version` is null)) or ((`volume` is not null) and (`volume_unit_key` is not null) and (`volume_unit_version` is not null))) is true)'
        show = '  CONSTRAINT `ck_test` CHECK (' + actual + ')'
        self.assertTrue(self.compare(expected, actual, show, True)['equal'])
        for changed in (actual.replace('`volume`', '`wrong_volume`'),
                        actual.replace('is not null', 'is null', 1),
                        actual.replace(' or ', ' and ', 1), actual.replace(' is true', ''),
                        '(`unit_contract_version` is null) is true'):
            self.assertFalse(self.compare(expected, changed, '  CONSTRAINT `ck_test` CHECK (' + changed + ')', True)['equal'])
        self.assertFalse(self.compare(expected, actual, show.replace('ck_test', 'ck_wrong'), True)['equal'])
        self.assertFalse(self.compare(expected, actual, show + '\n' + show, True)['equal'])

    def test_exact_volume_semantics_against_independent_fixture(self):
        from market_units_schema_fixture import CheckExpression as IndependentExpression
        expected = '(unit_contract_version IS NULL OR ((volume IS NULL AND volume_unit_key IS NULL AND volume_unit_version IS NULL) OR (volume IS NOT NULL AND volume_unit_key IS NOT NULL AND volume_unit_version IS NOT NULL))) IS TRUE'
        actual = '((unit_contract_version IS NULL OR (volume IS NULL AND volume_unit_key IS NULL AND volume_unit_version IS NULL)) OR (volume IS NOT NULL AND volume_unit_key IS NOT NULL AND volume_unit_version IS NOT NULL)) IS TRUE'
        a, b = IndependentExpression(expected), IndependentExpression(actual)
        for flags in itertools.product((False, True), repeat=4):
            row = {field: 1 if flag else None for field, flag in zip(('unit_contract_version', 'volume', 'volume_unit_key', 'volume_unit_version'), flags)}
            self.assertEqual(a.evaluate(row), b.evaluate(row))

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

    def test_practical_review_requires_verified_structure_and_empty_owned_schema(self):
        script = r'''
require $argv[1];
$counts=['tables'=>13,'columns'=>96,'primary'=>13,'unique'=>7,'secondary'=>16,'foreign_keys'=>14,'checks'=>9];
$rows=array_fill_keys(\Mosa2\Phase2\TABLES,0);
$results=[\Mosa2\Phase2\reviewablePostcheck('practical',$counts,$rows)];
foreach(['ddl','structure','ledger'] as $stage)$results[]=\Mosa2\Phase2\reviewablePostcheck($stage,$counts,$rows);
$changed=$rows;$changed['m2_entities']=1;$results[]=\Mosa2\Phase2\reviewablePostcheck('practical',$counts,$changed);
$changed=$rows;$changed['m2_schema_migrations']=1;$results[]=\Mosa2\Phase2\reviewablePostcheck('practical',$counts,$changed);
$changed=$rows;$changed['foreign']=0;$results[]=\Mosa2\Phase2\reviewablePostcheck('practical',$counts,$changed);
$changed=$counts;$changed['foreign_keys']=13;$results[]=\Mosa2\Phase2\reviewablePostcheck('practical',$changed,$rows);
echo json_encode($results);
'''
        result=subprocess.run(['php','-r',script,str(ROOT/'scripts/phase2/postcheck.php')],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(result.stdout), [True]+[False]*7)

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
