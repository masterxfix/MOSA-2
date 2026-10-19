"""Phase 3J schema-only contract: no database connection or migration execution."""
from decimal import Decimal
import hashlib
import itertools
import re
import unittest

from test_core_schema_phase2 import ROOT, MIGRATIONS, split_sql
from market_units_schema_fixture import CheckExpression, foreign_keys_accept, parse_schema

FILES = ['0001_core_asset_identity.sql', '0002_market_current_history.sql', '0003_market_units.sql']
BASE = ''.join((MIGRATIONS / name).read_text(encoding='utf-8') for name in FILES[:2])
SQL = (MIGRATIONS / FILES[2]).read_text(encoding='utf-8')
BEFORE, AFTER = parse_schema(BASE), parse_schema(BASE + SQL)
CONTRACT = 'mosa2-market-unit-v1'
ROUTES = 'm2_asset_source_routes'
OBS = 'm2_market_observations'
CURRENT = 'm2_market_current'
BARS = 'm2_market_bars'
FACTS = (OBS, CURRENT, BARS)
AFFECTED = (ROUTES,) + FACTS
UNIT_FIELDS = {'unit_contract_version', 'quote_unit_key', 'quote_unit_version',
               'quantity_basis_unit_key', 'quantity_basis_unit_version', 'quantity_basis_amount',
               'volume_unit_key', 'volume_unit_version'}
PROTECTED = {
    'docs/database/migrations/0001_core_asset_identity.sql': '9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd',
    'docs/database/migrations/0002_market_current_history.sql': '205bea42cfc93a64f76eb61c10377e47dceae38815c4351817a17aced00a75ee',
    'scripts/phase3c/market_flow.php': 'ab2b9510da0a76b549b587e10db5d768f079b57cd1d4e0d6542b46f805cd33af',
    'tests/test_phase3c.py': '9e4f03f8bbb4cc969553df906940b94ef020ef3b3d7af571a048cec8d1f1b940',
    'index.html': 'e2d87e36d84703e7fa6e0c629ffb2a3b89451ff45602d15651bf1e69e3099c05',
    'assets/css/main.css': '6b500107f2be65f11dd49be06375f76cb0b4488a5b9f0636ab44b673c604e319',
    'assets/js/page_load_time.js': 'd892ccee43c03989a66edd65e929c83a536747dbc3bd7da3720f8c147d938593',
}


def new_checks(table, schema=AFTER):
    old = BEFORE.get(table, {}).get('checks', {})
    return [CheckExpression(value) for key, value in schema[table]['checks'].items() if key not in old]


def accepts(table, row, schema=AFTER):
    # New CHECKs are deliberately stronger than MySQL's ordinary TRUE-or-UNKNOWN.
    return all(check.evaluate(row) is True for check in new_checks(table, schema))


def legacy(table):
    row = dict.fromkeys(AFTER[table]['columns'])
    row.update(currency='EUR', route_revision=1, volume=Decimal('12'), day_volume=Decimal('12'))
    return row


def aware(table):
    row = legacy(table)
    row.update(unit_contract_version=CONTRACT, quote_unit_key='POINT', quote_unit_version=1,
               currency=None, volume=None, day_volume=None)
    if table == OBS:
        row['observation_format_version'] = 2
    return row


def unit(key='EUR', base=None, denominator=1, currency='EUR', dimension='monetary'):
    return dict(unit_key=key, unit_version=1, unit_contract_version=CONTRACT,
                dimension_key=dimension, base_unit_key=base or key, base_unit_version=1,
                monetary_currency_code=currency, scale_numerator=1, scale_denominator=denominator,
                definition_sha256=b'x' * 32, status='frozen', created_at='2026-01-01 00:00:00.000000')


class MarketUnitsSchemaTests(unittest.TestCase):
    def test_protected_artifacts_are_byte_identical(self):
        for path, expected in PROTECTED.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)

    def test_exact_migration_inventory_and_schema_only_statements(self):
        self.assertEqual(sorted(p.name for p in MIGRATIONS.glob('*.sql')), FILES)
        body = re.sub(r'^\s*--[^\n]*$', '', SQL, flags=re.M)
        statements = split_sql(body, ';')[:-1]
        self.assertEqual(len(statements), 5)
        self.assertTrue(statements[0].startswith('CREATE TABLE m2_units'))
        self.assertEqual([re.match(r'ALTER TABLE (\w+)', s)[1] for s in statements[1:]], list(AFFECTED))
        # ON DELETE RESTRICT is an FK action, not a data DELETE statement.
        self.assertNotRegex(body.upper().replace('ON DELETE RESTRICT', ''),
                            r'\b(INSERT|UPDATE|DELETE|REPLACE|SELECT|USE|SET|TRIGGER|PROCEDURE|IF|FLOAT|DOUBLE)\b')
        self.assertIn('NOT applied live', SQL)
        self.assertIn('8.0.26-16', SQL)
        self.assertIn('UTC', SQL)
        self.assertIn('strict', SQL)

    def test_final_schema_inventory(self):
        self.assertEqual(set(AFTER) - set(BEFORE), {'m2_units'})
        totals = (len(AFTER), sum(len(t['columns']) for t in AFTER.values()),
                  sum(t['pk'] is not None for t in AFTER.values()),
                  sum(sum(v[1] for v in t['indexes'].values()) for t in AFTER.values()),
                  sum(sum(not v[1] for v in t['indexes'].values()) for t in AFTER.values()),
                  sum(len(t['fks']) for t in AFTER.values()), sum(len(t['checks']) for t in AFTER.values()))
        self.assertEqual(totals, (17, 186, 17, 10, 39, 36, 37))

    def test_catalog_exact_columns_and_reference_contract(self):
        table = AFTER['m2_units']
        self.assertEqual(set(table['columns']), {'unit_key', 'unit_version', 'unit_contract_version',
                         'dimension_key', 'base_unit_key', 'base_unit_version', 'monetary_currency_code',
                         'scale_numerator', 'scale_denominator', 'definition_sha256', 'status', 'created_at'})
        self.assertEqual(table['pk'], ('unit_key', 'unit_version'))
        self.assertEqual(table['indexes']['uq_units_contract'], (('unit_key', 'unit_version', 'unit_contract_version'), True))
        self.assertEqual(table['fks']['fk_units_base'], (('base_unit_key', 'base_unit_version', 'unit_contract_version'),
                         'm2_units', ('unit_key', 'unit_version', 'unit_contract_version'), 'RESTRICT'))
        for field in ('scale_numerator', 'scale_denominator'):
            self.assertEqual(table['columns'][field][:2], ('DECIMAL(38,0)', False))
        self.assertEqual(table['columns']['definition_sha256'][:2], ('BINARY(32)', False))
        self.assertEqual(table['columns']['created_at'][:2], ('DATETIME(6)', False))
        self.assertEqual([k for k, v in table['columns'].items() if v[1]], ['monetary_currency_code'])

    def test_only_intended_existing_columns_keys_and_constraints_change(self):
        for name, old in BEFORE.items():
            table = AFTER[name]
            self.assertEqual(table['pk'], old['pk'])
            for column, definition in old['columns'].items():
                expected = list(definition)
                if name in FACTS and column == 'currency':
                    expected[1] = True
                self.assertEqual(table['columns'][column], tuple(expected), (name, column))
            for section in ('fks', 'checks', 'indexes'):
                for key, value in old[section].items():
                    if name == ROUTES and key in ('uq_routes_external', 'uq_routes_asset_source'):
                        self.assertNotIn(key, table[section])
                    else:
                        self.assertEqual(table[section][key], value)
            if name not in AFFECTED:
                self.assertEqual(table, old)

    def test_revision_unique_replacement_is_one_statement(self):
        table = AFTER[ROUTES]
        self.assertEqual(table['columns']['route_revision'], ('INT UNSIGNED', False, None, False, '1'))
        for key, columns in (
                ('uq_routes_external_revision', ('source_id', 'route_type', 'external_key', 'route_revision')),
                ('uq_routes_asset_source_revision', ('asset_id', 'source_id', 'route_type', 'route_revision'))):
            self.assertEqual(table['indexes'][key], (columns, True))
        route_sql = SQL.split('ALTER TABLE ' + ROUTES)[1].split(';')[0]
        self.assertEqual(route_sql.count('DROP INDEX'), 2)
        self.assertLess(route_sql.index('ADD UNIQUE'), route_sql.index('DROP INDEX'))
        for revision in (0, -1, None):
            self.assertFalse(accepts(ROUTES, dict(legacy(ROUTES), route_revision=revision)))

    def test_nullable_bindings_and_complete_contract_fks(self):
        for name in AFFECTED:
            expected = UNIT_FIELDS.copy()
            if name == CURRENT:
                expected -= {'volume_unit_key', 'volume_unit_version'}
                expected |= {'day_volume_unit_key', 'day_volume_unit_version'}
            extras = set(AFTER[name]['columns']) - set(BEFORE[name]['columns'])
            self.assertEqual(extras, expected | ({'route_revision'} if name == ROUTES else
                                               {'observation_format_version'} if name == OBS else set()))
            for field in expected:
                self.assertTrue(AFTER[name]['columns'][field][1])
            self.assertEqual(AFTER[name]['columns']['quantity_basis_amount'][0], 'DECIMAL(32,8)')
            new_fks = [value for key, value in AFTER[name]['fks'].items() if key not in BEFORE[name]['fks']]
            self.assertEqual(len(new_fks), 3)
            for columns, parent, target, action in new_fks:
                self.assertEqual(columns[-1], 'unit_contract_version')
                self.assertEqual((parent, target, action), ('m2_units', ('unit_key', 'unit_version', 'unit_contract_version'), 'RESTRICT'))
        self.assertEqual(AFTER[OBS]['columns']['observation_format_version'][:2], ('SMALLINT UNSIGNED', True))

    def test_new_check_identifiers_and_unknown_are_closed(self):
        for name in (*AFFECTED, 'm2_units'):
            for check in new_checks(name):
                self.assertLessEqual(check.fields, AFTER[name]['columns'].keys())
                self.assertEqual(check.tree[0], 'true')
        self.assertIsNone(CheckExpression('value > 0').evaluate({'value': None}))
        self.assertIs(CheckExpression('(value > 0) IS TRUE').evaluate({'value': None}), False)

    def test_legacy_rows_with_populated_volumes_preserve_currency(self):
        for name in AFFECTED:
            self.assertTrue(accepts(name, legacy(name)))
            if name in FACTS:
                self.assertFalse(accepts(name, dict(legacy(name), currency=None)))
                self.assertTrue(accepts(name, aware(name)))  # POINT has no pseudocurrency

    def test_all_marker_and_quote_null_combinations(self):
        for name in AFFECTED:
            fields = ['unit_contract_version', 'quote_unit_key', 'quote_unit_version']
            values = [CONTRACT, 'EUR', 1]
            if name == OBS:
                fields += ['observation_format_version']
                values += [2]
            for present in itertools.product((False, True), repeat=len(fields)):
                row = legacy(name)
                row.update({k: v if yes else None for k, v, yes in zip(fields, values, present)})
                row.update(volume=None, day_volume=None)
                self.assertEqual(accepts(name, row), all(present) or not any(present), (name, present))
            if name == OBS:
                for version in (0, 1, 3):
                    self.assertFalse(accepts(name, dict(aware(name), observation_format_version=version)))

    def test_quantity_all_or_none_exhaustive_and_positive(self):
        fields = ('quantity_basis_unit_key', 'quantity_basis_unit_version', 'quantity_basis_amount')
        for name in AFFECTED:
            for bits in itertools.product((False, True), repeat=3):
                row = aware(name)
                row.update({k: value if bit else None for k, value, bit in zip(fields, ('SHARE', 1, Decimal('100')), bits)})
                self.assertEqual(accepts(name, row), all(bits) or not any(bits), (name, bits))
            for amount in (Decimal('0'), Decimal('-0.00000001')):
                row = dict(aware(name), quantity_basis_unit_key='SHARE', quantity_basis_unit_version=1, quantity_basis_amount=amount)
                self.assertFalse(accepts(name, row))

    def test_volume_all_or_none_and_value_binding_exhaustive(self):
        for name in AFFECTED:
            prefix = 'day_volume' if name == CURRENT else 'volume'
            for bits in itertools.product((False, True), repeat=3):
                has_value, key, version = bits
                row = aware(name)
                row.update({prefix: Decimal('0') if has_value else None,
                            prefix + '_unit_key': 'SHARE' if key else None,
                            prefix + '_unit_version': 1 if version else None})
                expected = (key == version) if name == ROUTES else (has_value == key == version)
                self.assertEqual(accepts(name, row), expected, (name, bits))

    def test_synthetic_catalog_rationals_and_nonmonetary_case(self):
        catalog = [unit(), unit('GBP', currency='GBP'), unit('GBX', 'GBP', 100, 'GBP'),
                   unit('POINT', currency=None, dimension='index_point')]
        for row in catalog:
            self.assertTrue(accepts('m2_units', row))
            self.assertTrue(foreign_keys_accept(AFTER['m2_units'], row, catalog))
        self.assertEqual(Decimal(catalog[2]['scale_numerator']) / Decimal(catalog[2]['scale_denominator']), Decimal('0.01'))
        for changes in ({'scale_denominator': 0}, {'scale_numerator': -1}, {'unit_version': 0},
                        {'base_unit_version': 0}, {'status': 'draft'}, {'unit_contract_version': 'other'},
                        {'unit_key': ''}, {'monetary_currency_code': None}, {'dimension_key': 'index_point'}):
            self.assertFalse(accepts('m2_units', dict(unit(), **changes)), changes)

    def test_fks_bind_definition_version_and_contract(self):
        catalog = [unit('POINT', currency=None, dimension='index_point')]
        for name in AFFECTED:
            self.assertTrue(foreign_keys_accept(AFTER[name], aware(name), catalog))
            for changes in ({'unit_contract_version': 'other'}, {'quote_unit_version': 0},
                            {'quote_unit_version': 2}, {'quote_unit_key': 'MISSING'}):
                self.assertFalse(foreign_keys_accept(AFTER[name], dict(aware(name), **changes), catalog))

    def test_parser_rejects_unconsumed_ddl_and_broken_references(self):
        for suffix in (' SELECT 1;', ' INSERT INTO m2_units VALUES (1);', ' COMMIT;', ' /* ignored? */',
                       ' ALTER TABLE m2_units ADD nonsense;', ' ALTER TABLE m2_units DROP INDEX missing;'):
            with self.assertRaises(ValueError):
                parse_schema(BASE + SQL + suffix)
        for old, new in [('quote_unit_key VARCHAR(64)', 'quote_unit_key VARCHAR(63)'),
                         ('ADD KEY ix_routes_quote_unit', 'ADD KEY ix_routes_quote_unit_broken'),
                         ('REFERENCES m2_units (unit_key, unit_version, unit_contract_version)',
                          'REFERENCES m2_units (unit_key, unit_version, dimension_key)')]:
            mutated = SQL.replace(old, new, 1)
            if 'broken' in new:  # Removing the supporting index must be rejected.
                mutated = re.sub(r'    ADD KEY ix_routes_quote_unit_broken [^\n]+\n', '', mutated)
            with self.assertRaises(ValueError):
                parse_schema(BASE + mutated)

    def test_check_mutation_changes_real_sql_semantics(self):
        mutated = parse_schema(BASE + SQL.replace('quantity_basis_amount > 0', 'quantity_basis_amount >= 0'))
        row = dict(aware(OBS), quantity_basis_unit_key='SHARE', quantity_basis_unit_version=1, quantity_basis_amount=0)
        self.assertFalse(accepts(OBS, row))
        self.assertTrue(accepts(OBS, row, mutated))
        for malformed in ('(x IS NULL) IS TRUE trailing', 'x + 1', 'x IS FALSE', '(x IS NULL'):
            with self.assertRaises(ValueError):
                CheckExpression(malformed)


if __name__ == '__main__':
    unittest.main()
