"""Offline production-validator tests and independent canonical-byte vectors."""
import ast
import copy
import hashlib
import importlib.util
import json
import locale
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'scripts/phase3l/unit_seed.py'
spec = importlib.util.spec_from_file_location('unit_seed_phase3l', MODULE)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)
MANIFEST = seed.load_manifest()
HASHES = {
    'EUR': '4d2e721264795c68d1d5434cdab7c53199ba4270c1cd43114200f9e86de1c4c4',
    'GBP': 'dcf7b65464052cd34b4e98a0fc7abcf32b53543117af2a612965f0ed3f4fb10a',
    'POINT': '29c50d2fad8e5176e9c4204579c1b33b9e7883f3afe8fe3cbfc097efd72b7092',
    'GBX': 'c80d04b9e0b1ee996242364ffbfea7b37fbda9c23f746356072b43cce551ddd6',
}
PACKAGE = 'b66df6f972ad13c05c3f34c604088c0281dcd9f0ff4bafad45b9600aa2b747ee'
PROTECTED = {
    'docs/database/migrations/0003_market_units.sql': '199933884802bd139b706e50e57e04687e9cbe5f8bd1366e98e302af7d47b8ee',
    'scripts/phase3c/market_flow.php': 'ab2b9510da0a76b549b587e10db5d768f079b57cd1d4e0d6542b46f805cd33af',
    'index.html': 'f271e50a25fe7dadac9f4e76f0dfb1ce0264d21476e6cb09125ad5deb6c2f4d6',
    'assets/css/main.css': '89859971c23d555112fc5052d5fcdf6b1b93617c9613e26fe3d369ff9b7c8ea1',
    'assets/js/page_load_time.js': 'd892ccee43c03989a66edd65e929c83a536747dbc3bd7da3720f8c147d938593',
}


class UnitSeedTests(unittest.TestCase):
    def setUp(self):
        self.rows = copy.deepcopy(MANIFEST['definitions'])

    def reject(self, **changes):
        rows = copy.deepcopy(self.rows)
        row = rows[-1]
        row.update(changes)
        # Isolate structural rejection from integrity checks wherever possible.
        try:
            row['definition_sha256'] = seed.definition_sha256(row)
        except ValueError:
            pass
        with self.assertRaises(ValueError):
            seed.validate_definitions(rows)

    def test_four_exact_normative_rows(self):
        expected = [('EUR', 'EUR', 'monetary', 'EUR', '1'),
                    ('GBP', 'GBP', 'monetary', 'GBP', '1'),
                    ('POINT', 'POINT', 'index_point', None, '1'),
                    ('GBX', 'GBP', 'monetary', 'GBP', '100')]
        self.assertEqual(len(self.rows), 4)
        for row, (key, base, dimension, currency, denominator) in zip(self.rows, expected):
            with self.subTest(key=key):
                self.assertEqual([row[k] for k in seed.FIELDS],
                                 [key, '1', seed.CONTRACT, dimension, base, '1', currency, '1', denominator, 'frozen'])
                self.assertEqual(row['definition_sha256'], HASHES[key])
                self.assertNotIn('XXX', row.values())

    def test_independent_canonical_vector_and_binary_size(self):
        raw = (b'mosa2-unit-definition-v1\n{"unit_key":"GBX","unit_version":"1",'
               b'"unit_contract_version":"mosa2-market-unit-v1","dimension_key":"monetary",'
               b'"base_unit_key":"GBP","base_unit_version":"1","monetary_currency_code":"GBP",'
               b'"scale_numerator":"1","scale_denominator":"100","status":"frozen"}')
        self.assertEqual(seed.canonical_definition(self.rows[-1]), raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), HASHES['GBX'])
        self.assertEqual(len(bytes.fromhex(HASHES['GBX'])), 32)
        self.assertIn(b'"monetary_currency_code":null', seed.canonical_definition(self.rows[2]))

    def test_insert_order_bases_before_dependents(self):
        self.assertEqual([r['unit_key'] for r in seed.validate_definitions(self.rows[::-1])],
                         ['EUR', 'GBP', 'POINT', 'GBX'])

    def test_exact_rational_projection_preserves_native(self):
        native = '12345'
        self.assertEqual(seed.project_exact(native, self.rows[-1]), '123.45')
        self.assertEqual(native, '12345')
        for row in self.rows[:3]:
            self.assertEqual(seed.project_exact('12345.125', row), '12345.125')
        self.assertEqual(seed.project_exact('-12345', self.rows[-1]), '-123.45')
        self.assertEqual(seed.project_exact('0', self.rows[-1]), '0')

    def test_projection_unrepresentable_instead_of_rounding(self):
        row = dict(self.rows[-1], scale_denominator='3')
        for native, scale in [('1', 8), ('0.00000001', 8), ('1', 0)]:
            with self.assertRaisesRegex(ValueError, 'normalization_unrepresentable'):
                seed.project_exact(native, row, scale)
        for native in (1.2, '1e2', '1.000000001', '1000000000000000000000000'):
            with self.assertRaises(ValueError):
                seed.project_exact(native, self.rows[0])

    def test_denominator_zero(self):
        self.reject(scale_denominator='0')

    def test_negative_factors(self):
        for field in ('scale_numerator', 'scale_denominator'):
            with self.subTest(field=field):
                self.reject(**{field: '-1'})

    def test_unreduced_factor(self):
        self.reject(scale_numerator='2', scale_denominator='200')

    def test_float_boolean_fraction_exponent_rejected(self):
        for field in ('unit_version', 'base_unit_version', 'scale_numerator', 'scale_denominator'):
            for bad in (1.0, True, None, '1.0', '1e2', '01', '+1', ' 1', '1\n'):
                with self.subTest(field=field, bad=bad):
                    self.reject(**{field: bad})

    def test_sql_integer_bounds(self):
        for field in ('unit_version', 'base_unit_version'):
            self.reject(**{field: '4294967296'})
        for field in ('scale_numerator', 'scale_denominator'):
            self.reject(**{field: '1' + '0' * 38})
        row = dict(self.rows[-1], unit_version=4294967295, scale_numerator='9' * 38,
                   scale_denominator='1')
        self.assertEqual(seed.normalize_definition(row)['unit_version'], '4294967295')

    def test_missing_base(self):
        self.reject(base_unit_key='MISSING')

    def test_dimension_mismatch(self):
        self.reject(dimension_key='quantity', monetary_currency_code=None)

    def test_currency_mismatch(self):
        self.reject(monetary_currency_code='EUR')

    def test_currency_required_or_null(self):
        self.reject(monetary_currency_code=None)
        self.reject(monetary_currency_code='XXX')
        self.reject(monetary_currency_code='gbp')
        self.reject(dimension_key='index_point')

    def test_self_base_requires_identity_factor(self):
        self.reject(base_unit_key='GBX')

    def test_cycle_rejected(self):
        self.rows[1]['base_unit_key'] = 'GBX'
        self.rows[1]['definition_sha256'] = seed.definition_sha256(self.rows[1])
        with self.assertRaisesRegex(ValueError, 'chains/cycles'):
            seed.validate_definitions(self.rows)

    def test_three_unit_chain_rejected(self):
        row = dict(self.rows[-1], unit_key='MINOR', base_unit_key='GBX')
        row['definition_sha256'] = seed.definition_sha256(row)
        with self.assertRaisesRegex(ValueError, 'chains/cycles'):
            seed.validate_definitions(self.rows + [row])

    def test_duplicate_identity_rejected_after_normalization(self):
        row = dict(self.rows[0], unit_version=1)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            seed.validate_definitions(self.rows + [row])

    def test_unknown_missing_fields_and_bad_keys(self):
        for field in ('provider', 'ticker', 'route', 'price', 'asset_id', 'fx_rate'):
            self.reject(**{field: 'forbidden'})
        for field in seed.FIELDS:
            row = dict(self.rows[0]); del row[field]
            with self.assertRaises(ValueError):
                seed.normalize_definition(row)
        for bad in ('', 'gbx', 'G B', 'GÉ', 'X' * 65, 'GBP\n'):
            self.reject(unit_key=bad)
        self.reject(unit_version='0')
        self.reject(base_unit_version='0')
        self.reject(dimension_key='')
        self.reject(status='draft')
        self.reject(unit_contract_version='mosa2-market-unit-v2')

    def test_definition_and_package_tampering_rejected(self):
        self.rows[-1]['definition_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            seed.validate_definitions(self.rows)
        manifest = copy.deepcopy(MANIFEST); manifest['package_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
            seed.validate_manifest(manifest)

    def test_hash_independent_of_input_order_whitespace_integer_encoding(self):
        for row in self.rows:
            shuffled = dict(reversed(list(row.items())))
            shuffled['unit_version'] = 1
            shuffled = json.loads(json.dumps(shuffled, indent=7))
            self.assertEqual(seed.definition_sha256(shuffled), row['definition_sha256'])

    def test_evidence_and_creation_excluded_from_definition_hash(self):
        row = self.rows[-1]
        for timestamp in ('2026-10-20 00:00:00.000000', '2026-10-21 01:02:03.456789'):
            changed = dict(row, definition_reference='another public reference', created_at=timestamp)
            self.assertEqual(seed.definition_sha256(changed), row['definition_sha256'])

    def test_every_semantic_field_binds_hash(self):
        row = self.rows[-1]
        changes = dict(unit_key='MINOR', unit_version='2', dimension_key='quantity',
                       base_unit_key='EUR', base_unit_version='2', monetary_currency_code='EUR',
                       scale_numerator='3', scale_denominator='101')
        for field, value in changes.items():
            changed = dict(row, **{field: value})
            if field == 'dimension_key':
                changed['monetary_currency_code'] = None
            self.assertNotEqual(seed.definition_sha256(changed), row['definition_sha256'])
        # Unsupported contracts/statuses fail closed; canonical field serialization
        # still demonstrably binds their bytes, without weakening the allowlist.
        for field, value in [('unit_contract_version', 'mosa2-market-unit-v2'), ('status', 'draft')]:
            changed = seed.normalize_definition(row); changed[field] = value
            digest = hashlib.sha256((seed.DOMAIN + '\n' + seed.compact(changed)).encode()).hexdigest()
            self.assertNotEqual(digest, row['definition_sha256'])
            with self.assertRaises(ValueError):
                seed.definition_sha256(changed)

    def test_locale_independent(self):
        previous = locale.setlocale(locale.LC_ALL)
        try:
            tested = 0
            for candidate in ('C', '', 'C.UTF-8', 'de_DE.UTF-8', 'German_Germany.1252'):
                try:
                    locale.setlocale(locale.LC_ALL, candidate)
                except locale.Error:
                    continue
                tested += 1
                self.assertEqual(seed.package_sha256(MANIFEST), PACKAGE)
            self.assertGreaterEqual(tested, 2)
        finally:
            locale.setlocale(locale.LC_ALL, previous)

    def test_package_fingerprint_stability_and_complete_binding(self):
        self.assertEqual(seed.package_sha256(MANIFEST), PACKAGE)
        changed = copy.deepcopy(MANIFEST); changed['definitions'].reverse()
        self.assertEqual(seed.package_sha256(changed), PACKAGE)
        for field, value in [('package_key', 'other'), ('package_version', '2')]:
            changed = copy.deepcopy(MANIFEST); changed[field] = value
            self.assertNotEqual(seed.package_sha256(changed), PACKAGE)
        for field, value in [('definition_reference', 'changed evidence'), ('scale_denominator', '101')]:
            changed = copy.deepcopy(MANIFEST); changed['definitions'][-1][field] = value
            changed['definitions'][-1]['definition_sha256'] = seed.definition_sha256(changed['definitions'][-1])
            self.assertNotEqual(seed.package_sha256(changed), PACKAGE)

    def test_two_processes_different_workdirs_identical_output(self):
        with tempfile.TemporaryDirectory() as directory:
            commands = [subprocess.run([sys.executable, str(MODULE)], cwd=cwd, capture_output=True, check=True)
                        for cwd in (ROOT, directory)]
        self.assertEqual(commands[0].stdout, commands[1].stdout)
        self.assertEqual(json.loads(commands[0].stdout)['package_sha256'], PACKAGE)

    def test_load_whitespace_key_order_crlf_and_duplicate_members(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            changed = dict(reversed(list(MANIFEST.items())))
            path.write_bytes(json.dumps(changed, indent=4).replace('\n', '\r\n').encode())
            self.assertEqual(seed.load_manifest(path), MANIFEST)
            path.write_text('{"manifest_format":"a","manifest_format":"b"}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
                seed.load_manifest(path)

    def test_no_connection_execution_or_unit_special_case(self):
        tree = ast.parse(MODULE.read_text(encoding='utf-8'))
        imports = {n.name.split('.')[0] for node in ast.walk(tree)
                   if isinstance(node, (ast.Import, ast.ImportFrom))
                   for n in (node.names if isinstance(node, ast.Import) else [])}
        imports |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(imports, {'argparse', 'datetime', 'hashlib', 'json', 'math', 'fractions', 'pathlib', 're'})
        source = MODULE.read_text(encoding='utf-8')
        for forbidden in ('EUR', 'GBP', 'GBX', 'POINT', 'INSERT', 'execute(', 'connect(', 'PDO', 'mysqli'):
            self.assertNotIn(forbidden, source)

    def test_protected_source_bytes(self):
        for path, expected in PROTECTED.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
