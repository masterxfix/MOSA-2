"""Offline Phase-3A DDL contracts and a test-only future write-path model.

Uses the existing restricted parser. No DB, collector, deployment or real data.
Model tests are not MySQL execution or a production tie-break implementation.
"""

from copy import deepcopy
from decimal import Decimal
import hashlib
import re
import unittest

from test_core_schema_phase2 import MIGRATIONS, ROOT, SQL as CORE_SQL, parse, specification_columns

SQL_PATH = MIGRATIONS / '0002_market_current_history.sql'
SQL = SQL_PATH.read_text(encoding='utf-8')
SPEC = (ROOT / 'docs/database/MARKET_DATA_PHASE3.md').read_text(encoding='utf-8')
# SHA-256 of raw migration 0001 at fe6c9d818778432dec458e12d70913c9fcbb5db0.
CORE_DIGEST = '9c3ac21f02fc242e9561d94aaa4a4c4fe6a430d11aa5f0681f0c9eace81446dd'
TABLES = {'m2_market_current', 'm2_market_observations', 'm2_market_bars'}
INDEXES = {
    'm2_market_current': {('source_id', 'observed_at', 'asset_id'), ('route_id',)},
    'm2_market_observations': {('asset_id', 'market_at', 'id'),
        ('asset_id', 'source_id', 'market_at', 'id'), ('source_id', 'observed_at', 'id'), ('route_id',)},
    'm2_market_bars': {('asset_id', 'interval_key', 'starts_at', 'id'),
        ('asset_id', 'source_id', 'interval_key', 'starts_at', 'id'),
        ('source_id', 'observed_at', 'id'), ('route_id',)},
}
UNIQUES = {'m2_market_current': set(), 'm2_market_observations': {('dedupe_key',)},
           'm2_market_bars': {('asset_id', 'route_id', 'interval_key', 'starts_at')}}
CHECKS = {
    'm2_market_current': {
        'ck_market_current_price': 'price > 0',
        'ck_market_current_bid_ask': 'bid <= ask',
        'ck_market_current_day_range': 'day_low <= day_high'},
    'm2_market_observations': {
        'ck_market_observations_price': 'price > 0',
        'ck_market_observations_bid_ask': 'bid <= ask'},
    'm2_market_bars': {
        'ck_market_bars_interval': "interval_key IN ('1m', '5m', '1h', '1d')",
        'ck_market_bars_time': 'starts_at < ends_at',
        'ck_market_bars_prices': 'open_price > 0 AND high_price > 0 AND low_price > 0 AND close_price > 0',
        'ck_market_bars_low': 'low_price <= open_price AND low_price <= close_price AND low_price <= high_price',
        'ck_market_bars_high': 'high_price >= open_price AND high_price >= close_price AND high_price >= low_price'},
}


class MarketSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tables = parse(SQL)

    def test_0001_raw_bytes_match_start_commit(self):
        self.assertEqual(hashlib.sha256((MIGRATIONS / '0001_core_asset_identity.sql').read_bytes()).hexdigest(), CORE_DIGEST)

    def test_exact_three_tables(self):
        self.assertTrue(SQL_PATH.is_file())
        self.assertEqual(set(self.tables), TABLES)
        self.assertEqual(set(specification_columns(SPEC)), TABLES)

    def test_exact_columns_types_nullability_no_provider_payload_or_secrets(self):
        for name, columns in specification_columns(SPEC).items():
            self.assertEqual({c: v[:2] for c, v in self.tables[name]['columns'].items()}, columns)

    def test_engine_charset_collation_and_machine_values(self):
        for table in self.tables.values():
            self.assertEqual((table['engine'], table['charset'], table['collation']),
                             ('InnoDB', 'utf8mb4', 'utf8mb4_0900_ai_ci'))
            for name, column in table['columns'].items():
                self.assertEqual(column[2], 'utf8mb4_0900_bin' if name in ('currency', 'interval_key') else None)
                self.assertFalse(column[4])  # No implicit defaults, including local timestamps.

    def test_primary_keys_and_auto_increment(self):
        for name, table in self.tables.items():
            current = name == 'm2_market_current'
            self.assertEqual(table['pk'], ('asset_id',) if current else ('id',))
            self.assertEqual([c for c, v in table['columns'].items() if v[3]], [] if current else ['id'])

    def test_exact_fks_restrict_and_parent_compatibility(self):
        parents = parse(CORE_SQL)
        expected = {'asset_id': ('m2_assets', 'entity_id', 'RESTRICT'),
                    'source_id': ('m2_sources', 'id', 'RESTRICT'),
                    'route_id': ('m2_asset_source_routes', 'id', 'RESTRICT')}
        for table in self.tables.values():
            self.assertEqual(table['fks'], expected)
            for column, (parent, target, _) in table['fks'].items():
                self.assertEqual(table['columns'][column][0], parents[parent]['columns'][target][0])
                self.assertEqual(parents[parent]['pk'], (target,))
                self.assertFalse(table['columns'][column][1])
                self.assertTrue(any(k[0] == column for k in table['indexes'] | table['unique'] | {table['pk']}))
        self.assertEqual(len(parse(CORE_SQL + SQL)), 16)  # Also catches cross-migration constraint-name collisions.

    def test_exact_unique_keys(self):
        for name, table in self.tables.items():
            self.assertEqual(table['unique'], UNIQUES[name])

    def test_exact_query_indexes(self):
        for name, table in self.tables.items():
            self.assertEqual(table['indexes'], INDEXES[name])

    def test_exact_checks_per_table(self):
        for name, table in self.tables.items():
            self.assertEqual(table['checks'], CHECKS[name])

    def test_decimal_financial_values_and_binary_dedupe(self):
        for table in self.tables.values():
            for name, column in table['columns'].items():
                if name in ('price', 'bid', 'ask', 'day_open', 'day_high', 'day_low', 'previous_close',
                            'open_price', 'high_price', 'low_price', 'close_price'):
                    self.assertEqual(column[0], 'DECIMAL(28,10)')
                if name in ('volume', 'day_volume'):
                    self.assertEqual(column[:2], ('DECIMAL(32,8)', True))
                self.assertNotRegex(column[0], r'FLOAT|DOUBLE')
        self.assertEqual(self.tables['m2_market_observations']['columns']['dedupe_key'],
                         ('BINARY(32)', False, None, False, False))

    def test_utc_microsecond_fields(self):
        count = 0
        for table in self.tables.values():
            for name, column in table['columns'].items():
                if name.endswith('_at'):
                    count += 1
                    self.assertEqual(column, ('DATETIME(6)', False, None, False, False))
        self.assertEqual(count, 10)
        self.assertIn('UTC', SQL)

    def test_every_index_column_exists_and_fits_mysql_limits(self):
        for table in self.tables.values():
            for key in table['indexes'] | table['unique'] | {table['pk']}:
                self.assertLessEqual(len(key), 16)
                size = 0
                for column in key:
                    datatype = table['columns'][column][0]
                    size += int(re.search(r'\((\d+)\)', datatype)[1]) * 4 if datatype.startswith(('CHAR', 'VARCHAR')) else 32 if datatype == 'BINARY(32)' else 8
                self.assertLessEqual(size, 3072)

    def test_no_data_ledger_settings_triggers_or_procedures(self):
        # Full parser consumption allows only the exact three table definitions.
        for extra in ('USE production;', 'INSERT INTO m2_schema_migrations VALUES (2);',
                      'UPDATE m2_market_current SET price=1;', 'DELETE FROM m2_assets;',
                      'DROP TABLE m2_assets;', 'SET GLOBAL sql_mode=1;',
                      'CREATE TRIGGER x BEFORE INSERT ON m2_market_current FOR EACH ROW SET @x=1;',
                      'CREATE PROCEDURE x() SELECT 1;', '/*!80000 DROP TABLE m2_assets */;'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse(SQL + '\n' + extra)

    def test_mutations_are_rejected_by_contract(self):
        mutations = [
            ('m2_market_current (', 'm2_market_cache (', 'test_exact_three_tables'),
            ('ON DELETE RESTRICT', 'ON DELETE CASCADE', 'test_exact_fks_restrict_and_parent_compatibility'),
            ('REFERENCES m2_assets (entity_id)', 'REFERENCES m2_entities (id)', 'test_exact_fks_restrict_and_parent_compatibility'),
            ('PRIMARY KEY (asset_id)', 'PRIMARY KEY (source_id)', 'test_primary_keys_and_auto_increment'),
            ('(dedupe_key)', '(dedupe_key, asset_id)', 'test_exact_unique_keys'),
            ('asset_id, route_id, interval_key, starts_at)', 'asset_id, interval_key, starts_at)', 'test_exact_unique_keys'),
            ('source_id, observed_at, asset_id)', 'observed_at, source_id, asset_id)', 'test_exact_query_indexes'),
            ('price > 0', 'price >= 0', 'test_exact_checks_per_table'),
            ("'1h', '1d'", "'1h', '1d', '1w'", 'test_exact_checks_per_table'),
            ('low_price <= close_price', 'low_price < close_price', 'test_exact_checks_per_table'),
            ('starts_at < ends_at', 'starts_at <= ends_at', 'test_exact_checks_per_table'),
            ('DECIMAL(28,10)', 'DECIMAL(20,2)', 'test_decimal_financial_values_and_binary_dedupe'),
            ('COLLATE utf8mb4_0900_bin', 'COLLATE utf8mb4_0900_ai_ci', 'test_engine_charset_collation_and_machine_values'),
            ('currency CHAR(3)', 'provider_symbol CHAR(3)', 'test_exact_columns_types_nullability_no_provider_payload_or_secrets'),
        ]
        for before, after, method in mutations:
            with self.subTest(change=after):
                self.assertIn(before, SQL)
                probe = MarketSchemaTests(method)
                probe.tables = parse(SQL.replace(before, after, 1))
                with self.assertRaises(AssertionError):
                    getattr(probe, method)()
        for datatype in ('FLOAT', 'DOUBLE', 'BINARY(16)', 'TIMESTAMP', 'DATETIME(3)'):
            before = 'DECIMAL(28,10)' if datatype in ('FLOAT', 'DOUBLE') else 'BINARY(32)' if datatype.startswith('BINARY') else 'DATETIME(6)'
            with self.subTest(datatype=datatype), self.assertRaises(ValueError):
                # Mutate executable DDL, not the DATETIME(6) explanatory comment.
                ddl = re.sub(r'^\s*--[^\n]*$', '', SQL, flags=re.M)
                parse(ddl.replace(before, datatype, 1))


def model_write(history, current, observation, routes, fail=False):
    """Synthetic test-only transaction model; no collector or database writes.

    Equal market times use the opaque dedupe digest as a stable illustrative
    tie-break, NOT a production priority rule or final identity algorithm.
    """
    if routes.get(observation['route_id']) != (observation['asset_id'], observation['source_id']):
        raise ValueError('route provenance')
    if observation['price'] <= 0:
        raise ValueError('price')
    key = observation['dedupe_key']
    if key in history:
        if history[key] != observation:
            raise ValueError('identity conflict')
        return
    next_history, next_current = deepcopy(history), deepcopy(current)
    next_history[key] = deepcopy(observation)
    previous = next_current.get(observation['asset_id'])
    if previous is None or (observation['market_at'], key) > (previous['market_at'], previous['dedupe_key']):
        next_current[observation['asset_id']] = deepcopy(observation)
    if fail:
        raise ValueError('synthetic transaction failure')
    history.clear()
    history.update(next_history)
    current.clear()
    current.update(next_current)


class MarketWriteModelTests(unittest.TestCase):
    def setUp(self):
        self.history, self.current = {}, {}
        self.routes = {3: (1, 2)}

    def sample(self, time=1, key=1, price='1.25'):
        return dict(asset_id=1, source_id=2, route_id=3, price=Decimal(price),
                    market_at=time, dedupe_key=bytes([key]) * 32)

    def write(self, row, **kwargs):
        model_write(self.history, self.current, row, self.routes, **kwargs)

    def test_history_dedupe_and_current_consistency(self):
        row = self.sample()
        self.write(row)
        self.write(row)
        self.assertEqual(len(self.history), 1)
        self.assertEqual(self.current[1], self.history[row['dedupe_key']])
        self.write(self.sample(time=2, key=2, price='2.50'))
        self.assertEqual(len(self.history), 2)
        self.assertEqual(self.history[row['dedupe_key']], row)
        self.assertEqual(self.current[1]['price'], Decimal('2.50'))

    def test_older_history_never_replaces_current(self):
        self.write(self.sample(time=2, key=2))
        self.write(self.sample(time=1, key=1))
        self.assertEqual(len(self.history), 2)
        self.assertEqual(self.current[1]['market_at'], 2)

    def test_equal_time_is_order_independent(self):
        for keys in ((1, 2), (2, 1)):
            self.history, self.current = {}, {}
            for key in keys:
                self.write(self.sample(key=key))
            self.assertEqual(self.current[1]['dedupe_key'], bytes([2]) * 32)
            self.assertEqual(len(self.history), 2)

    def test_failure_rolls_back_both_projections(self):
        self.write(self.sample())
        before = deepcopy((self.history, self.current))
        with self.assertRaises(ValueError):
            self.write(self.sample(time=2, key=2), fail=True)
        self.assertEqual((self.history, self.current), before)

    def test_invalid_input_and_dedupe_conflict_do_not_mutate(self):
        self.write(self.sample())
        before = deepcopy((self.history, self.current))
        for row in (self.sample(price='0'), self.sample(price='-1'),
                    dict(self.sample(), source_id=99), dict(self.sample(), asset_id=99),
                    self.sample(price='9')):
            with self.assertRaises(ValueError):
                self.write(row)
            self.assertEqual((self.history, self.current), before)


if __name__ == '__main__':
    unittest.main()
