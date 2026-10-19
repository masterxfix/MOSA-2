"""Offline contract checks, not a substitute for a MySQL apply/postcheck.

The deliberately restricted DDL parser consumes every statement and definition.
No database, network, third-party parser or migration runner is used.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / 'docs/database/migrations'
SQL = (MIGRATIONS / '0001_core_asset_identity.sql').read_text(encoding='utf-8')
SPEC = (ROOT / 'docs/database/CORE_SCHEMA_PHASE2.md').read_text(encoding='utf-8')
IDENT = r'[a-z][a-z0-9_]*'
TYPE = r'(?:BIGINT UNSIGNED|SMALLINT UNSIGNED|INT UNSIGNED|TINYINT\(1\)|VARCHAR\(\d+\)|CHAR\(\d+\)|DATETIME\(6\)|BINARY\(32\)|DECIMAL\(\d+,\d+\)|JSON)'


def split_sql(text, delimiter):
    """Split only outside balanced parentheses and single-quoted literals."""
    result, start, depth, quoted, pos = [], 0, 0, False, 0
    while pos < len(text):
        char = text[pos]
        if char == "'":
            if quoted and pos + 1 < len(text) and text[pos + 1] == "'":
                pos += 2
                continue
            quoted = not quoted
        elif not quoted:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth < 0:
                    raise ValueError('Unbalanced closing parenthesis')
            elif char == delimiter and depth == 0:
                result.append(text[start:pos].strip())
                start = pos + 1
        pos += 1
    if quoted or depth:
        raise ValueError('Unterminated literal or parentheses')
    result.append(text[start:].strip())
    return result


def names(value):
    parts = tuple(part.strip() for part in value.split(','))
    if not parts or any(not re.fullmatch(IDENT, part) for part in parts):
        raise ValueError('Invalid column list')
    return parts


def parse(sql):
    # Only full-line ordinary comments are allowed; executable comments fail.
    sql = re.sub(r'^\s*--[^\n]*$', '', sql, flags=re.M)
    statements = split_sql(sql, ';')
    if statements.pop() != '':
        raise ValueError('Missing final semicolon')
    tables, constraint_names = {}, set()
    for statement in statements:
        match = re.fullmatch(
            rf'CREATE TABLE ({IDENT})\s*\((.*)\) ENGINE=({IDENT}) DEFAULT CHARSET=({IDENT}) COLLATE=({IDENT})',
            statement, re.S | re.I,
        )
        if not match:
            raise ValueError('Unsupported statement or table options')
        name, body, engine, charset, collation = match.groups()
        if name in tables:
            raise ValueError('Duplicate table')
        table = dict(columns={}, pk=None, unique=set(), indexes=set(), fks={}, checks={},
                     engine=engine, charset=charset, collation=collation)
        key_names = set()
        for definition in split_sql(body, ','):
            column = re.fullmatch(
                rf'({IDENT}) ({TYPE})(?: COLLATE ({IDENT}))? (NOT NULL|NULL)( AUTO_INCREMENT)?( DEFAULT \'\')?',
                definition,
            )
            key = re.fullmatch(rf'(UNIQUE )?KEY ({IDENT}) \(([^()]+)\)', definition)
            pk = re.fullmatch(r'PRIMARY KEY \(([^()]+)\)', definition)
            fk = re.fullmatch(
                rf'CONSTRAINT ({IDENT}) FOREIGN KEY \(({IDENT})\) REFERENCES ({IDENT}) \(({IDENT})\) ON DELETE (RESTRICT|CASCADE|SET NULL)',
                definition,
            )
            check = re.fullmatch(rf'CONSTRAINT ({IDENT}) CHECK \((.+)\)', definition, re.S)
            if column:
                field, datatype, collate, nullable, auto, default = column.groups()
                if field in table['columns']:
                    raise ValueError('Duplicate column')
                table['columns'][field] = (datatype, nullable == 'NULL', collate, bool(auto), bool(default))
            elif pk:
                if table['pk'] is not None:
                    raise ValueError('Duplicate primary key')
                table['pk'] = names(pk[1])
            elif key:
                if key[2] in key_names:
                    raise ValueError('Duplicate index name')
                key_names.add(key[2])
                table['unique' if key[1] else 'indexes'].add(names(key[3]))
            elif fk or check:
                item = fk or check
                if item[1] in constraint_names:
                    raise ValueError('Duplicate constraint name')
                constraint_names.add(item[1])
                if fk:
                    if fk[2] in table['fks']:
                        raise ValueError('Duplicate FK column')
                    table['fks'][fk[2]] = (fk[3], fk[4], fk[5])
                else:
                    table['checks'][check[1]] = check[2]
            else:
                raise ValueError('Unsupported table definition: ' + definition)
        tables[name] = table
    return tables


def specification_columns(spec=SPEC):
    result = {}
    for match in re.finditer(r'### \d+\. `(m2_\w+)`\n(.*?)(?=\n### |\n## |\Z)', spec, re.S):
        columns = {}
        for row in re.finditer(r'^\| `(\w+)` \| ([^|]+) \|', match[2], re.M):
            datatype = row[2].strip()
            columns[row[1]] = (datatype.removesuffix(' NULL'), datatype.endswith(' NULL'))
        result[match[1]] = columns
    return result


UNIQUES = {
    'm2_sources': {('source_key',)}, 'm2_jobs': {('job_key',)},
    'm2_asset_identifiers': {('identifier_type', 'normalized_value', 'scope_key')},
    'm2_asset_source_routes': {('source_id', 'route_type', 'external_key'), ('asset_id', 'source_id', 'route_type')},
    'm2_schema_migrations': {('migration_key',)},
    'm2_sync_checkpoints': {('source_id', 'stream_key')},
}
INDEXES = {
    'm2_entities': {('entity_type', 'status', 'id'), ('canonical_name', 'id')},
    'm2_relationships': {('from_entity_id', 'relationship_type', 'valid_to', 'to_entity_id'),
                         ('to_entity_id', 'relationship_type', 'valid_to', 'from_entity_id'),
                         ('source_id', 'created_at', 'id')},
    'm2_files': {('entity_id', 'created_at', 'id'), ('source_id', 'created_at', 'id'), ('sha256',)},
    'm2_events': {('entity_id', 'occurred_at', 'id'), ('event_type', 'occurred_at', 'id'), ('source_id', 'observed_at', 'id')},
    'm2_job_runs': {('job_id', 'started_at', 'id'), ('status', 'started_at', 'id')},
    'm2_asset_identifiers': {('asset_id', 'identifier_type', 'valid_to', 'id'), ('source_id', 'created_at', 'id')},
    'm2_asset_source_routes': {('asset_id', 'enabled', 'priority', 'id')},
}
FKS = {
    'm2_relationships': {'from_entity_id': ('m2_entities', 'id'), 'to_entity_id': ('m2_entities', 'id'), 'source_id': ('m2_sources', 'id')},
    'm2_files': {'entity_id': ('m2_entities', 'id'), 'source_id': ('m2_sources', 'id')},
    'm2_events': {'entity_id': ('m2_entities', 'id'), 'source_id': ('m2_sources', 'id')},
    'm2_job_runs': {'job_id': ('m2_jobs', 'id')},
    'm2_assets': {'entity_id': ('m2_entities', 'id')},
    'm2_asset_identifiers': {'asset_id': ('m2_assets', 'entity_id'), 'source_id': ('m2_sources', 'id')},
    'm2_asset_source_routes': {'asset_id': ('m2_assets', 'entity_id'), 'source_id': ('m2_sources', 'id')},
    'm2_sync_checkpoints': {'source_id': ('m2_sources', 'id')},
}
CHECKS = {
    'ck_entities_status': "status IN ('active', 'inactive', 'archived')",
    'ck_sources_enabled': 'enabled IN (0, 1)',
    'ck_jobs_enabled': 'enabled IN (0, 1)',
    'ck_job_runs_status': "status IN ('running', 'completed', 'failed', 'cancelled')",
    'ck_job_runs_attempt': 'attempt_no >= 1',
    'ck_identifiers_primary': 'is_primary IN (0, 1)',
    'ck_identifiers_ticker_scope': "identifier_type <> 'ticker' OR CHAR_LENGTH(TRIM(scope_key)) > 0",
    'ck_identifiers_global_scope': "identifier_type NOT IN ('isin', 'wkn', 'figi') OR scope_key = ''",
    'ck_routes_enabled': 'enabled IN (0, 1)',
}


class CoreSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tables = parse(SQL)

    def test_exact_thirteen_tables_no_provider_or_universal_tables(self):
        expected = {'m2_' + name for name in ('entities', 'relationships', 'sources', 'files', 'events',
                    'jobs', 'job_runs', 'assets', 'asset_identifiers', 'asset_source_routes',
                    'schema_migrations', 'sync_checkpoints', 'module_state')}
        self.assertEqual(set(self.tables), expected)
        self.assertEqual(set(specification_columns()), expected)

    def test_all_columns_types_and_nullability_match_specification(self):
        for name, expected in specification_columns().items():
            with self.subTest(table=name):
                self.assertEqual({k: v[:2] for k, v in self.tables[name]['columns'].items()}, expected)

    def test_engine_charset_and_table_collation(self):
        for table in self.tables.values():
            self.assertEqual((table['engine'], table['charset'], table['collation']),
                             ('InnoDB', 'utf8mb4', 'utf8mb4_0900_ai_ci'))

    def test_human_text_and_exact_machine_collations(self):
        for table in self.tables.values():
            for name, column in table['columns'].items():
                if column[0].startswith(('VARCHAR', 'CHAR(')):
                    self.assertEqual(column[2], None if name in ('display_name', 'canonical_name') else 'utf8mb4_0900_bin')
                else:
                    self.assertIsNone(column[2])

    def test_primary_keys_and_auto_increment_exceptions(self):
        exceptions = {'m2_assets': 'entity_id', 'm2_schema_migrations': 'version', 'm2_module_state': 'module_key'}
        for name, table in self.tables.items():
            pk = exceptions.get(name, 'id')
            self.assertEqual(table['pk'], (pk,))
            self.assertFalse(table['columns'][pk][1])
            self.assertEqual([c for c, v in table['columns'].items() if v[3]], [] if name in exceptions else ['id'])

    def test_all_foreign_keys_targets_and_restrict(self):
        for name, table in self.tables.items():
            self.assertEqual(table['fks'], {c: (*target, 'RESTRICT') for c, target in FKS.get(name, {}).items()})

    def test_fk_order_types_and_index_coverage(self):
        seen = set()
        for name, table in self.tables.items():
            for column, (parent, target, _) in table['fks'].items():
                self.assertIn(parent, seen)
                self.assertEqual(table['columns'][column][0], self.tables[parent]['columns'][target][0])
                self.assertEqual(self.tables[parent]['pk'], (target,))
                keys = table['indexes'] | table['unique'] | {table['pk']}
                self.assertTrue(any(key[0] == column for key in keys))
            seen.add(name)

    def test_all_unique_constraints(self):
        for name, table in self.tables.items():
            self.assertEqual(table['unique'], UNIQUES.get(name, set()))

    def test_all_normal_query_indexes(self):
        for name, table in self.tables.items():
            self.assertEqual(table['indexes'], INDEXES.get(name, set()))

    def test_relationships_both_directions_and_validity(self):
        table = self.tables['m2_relationships']
        for first, last in [('from_entity_id', 'to_entity_id'), ('to_entity_id', 'from_entity_id')]:
            self.assertIn((first, 'relationship_type', 'valid_to', last), table['indexes'])
        for field in ('valid_from', 'valid_to'):
            self.assertEqual(table['columns'][field][:2], ('DATETIME(6)', True))

    def test_identifier_identity_includes_nonnull_scope_and_empty_default(self):
        table = self.tables['m2_asset_identifiers']
        self.assertIn(('identifier_type', 'normalized_value', 'scope_key'), table['unique'])
        self.assertEqual(table['columns']['scope_key'], ('VARCHAR(64)', False, 'utf8mb4_0900_bin', False, True))
        self.assertEqual(table['checks']['ck_identifiers_ticker_scope'], CHECKS['ck_identifiers_ticker_scope'])
        self.assertEqual(table['checks']['ck_identifiers_global_scope'], CHECKS['ck_identifiers_global_scope'])

    def test_source_job_and_checkpoint_uniqueness(self):
        for name in ('m2_sources', 'm2_jobs', 'm2_sync_checkpoints'):
            self.assertEqual(self.tables[name]['unique'], UNIQUES[name])

    def test_names_are_never_unique_or_primary_identity(self):
        for table in self.tables.values():
            for key in table['unique'] | {table['pk']}:
                self.assertFalse(set(key) & {'display_name', 'canonical_name', 'identifier_value'})

    def test_json_only_in_two_explicit_slots(self):
        actual = {(t, c) for t, table in self.tables.items() for c, v in table['columns'].items() if v[0] == 'JSON'}
        self.assertEqual(actual, {('m2_events', 'metadata_json'), ('m2_job_runs', 'summary_json')})

    def test_files_only_digest_not_payload(self):
        columns = self.tables['m2_files']['columns']
        self.assertEqual({c for c, v in columns.items() if 'BINARY' in v[0]}, {'sha256'})
        self.assertEqual(columns['sha256'][0], 'BINARY(32)')
        self.assertFalse(any('BLOB' in v[0] or 'TEXT' in v[0] for v in columns.values()))

    def test_no_secrets_prices_positions_or_generic_payload_columns(self):
        for table in self.tables.values():
            for name in table['columns']:
                self.assertIsNone(re.search(r'secret|token|password|credential|api_key|payload|attributes', name))
        self.assertFalse(set(self.tables['m2_assets']['columns']) & {'price', 'position', 'portfolio_value', 'external_key'})

    def test_checks_are_exact_and_supported(self):
        self.assertEqual({k: v for t in self.tables.values() for k, v in t['checks'].items()}, CHECKS)

    def test_every_key_column_exists_and_fits_mysql_limits(self):
        for table in self.tables.values():
            for key in table['indexes'] | table['unique'] | {table['pk']}:
                self.assertLessEqual(len(key), 16)
                size = 0
                for column in key:
                    datatype = table['columns'][column][0]
                    length = re.search(r'\((\d+)\)', datatype)
                    size += int(length[1]) * 4 if datatype.startswith(('VARCHAR', 'CHAR(')) else 32 if datatype == 'BINARY(32)' else 8
                self.assertLessEqual(size, 3072)

    def test_no_data_writes_globals_or_other_sql_statements(self):
        for extra in ('INSERT INTO m2_entities VALUES (1);', 'SET GLOBAL sql_mode = \'\';',
                      'USE production;', 'DROP DATABASE anything;', 'SET FOREIGN_KEY_CHECKS=0;',
                      'CREATE USER unsafe;', 'ALTER TABLE m2_entities ADD token TEXT;',
                      '/*!80000 DROP TABLE m2_entities */;'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse(SQL + '\n' + extra)

    def test_parser_rejects_malformed_or_unconsumed_definitions(self):
        for bad in (SQL.rstrip(';\n'), SQL.replace('PRIMARY KEY (id)', 'PRIMARY KEY (missing', 1),
                    SQL.replace('id BIGINT', 'token BLOB, id BIGINT', 1),
                    SQL.replace('created_at DATETIME(6) NOT NULL,', 'nonsense,', 1),
                    SQL + SQL, SQL.replace('PRIMARY KEY (id)', 'PRIMARY KEY (id), PRIMARY KEY (id)', 1)):
            with self.subTest(prefix=bad[:40]), self.assertRaises(ValueError):
                parse(bad)

    def test_parser_handles_literal_delimiters_and_nested_expressions(self):
        self.assertEqual(split_sql("a, fn('x,y;z', (1)), 'it''s fine'", ','),
                         ['a', "fn('x,y;z', (1))", "'it''s fine'"])
        for bad in ("'unclosed", 'x)', '(x'):
            with self.assertRaises(ValueError):
                split_sql(bad, ',')

    def test_contract_detects_safety_regressions(self):
        # Mutation checks demonstrate independent expectations, not SQL snapshots.
        mutations = [
            ('ON DELETE RESTRICT', 'ON DELETE CASCADE', 'test_all_foreign_keys_targets_and_restrict'),
            ('ENGINE=InnoDB', 'ENGINE=MyISAM', 'test_engine_charset_and_table_collation'),
            ('COLLATE utf8mb4_0900_bin', 'COLLATE utf8mb4_0900_ai_ci', 'test_human_text_and_exact_machine_collations'),
            ('(identifier_type, normalized_value, scope_key)', '(identifier_type, normalized_value)', 'test_all_unique_constraints'),
            ('to_entity_id, relationship_type, valid_to, from_entity_id', 'to_entity_id, from_entity_id', 'test_all_normal_query_indexes'),
            ('attempt_no >= 1', 'attempt_no >= 0', 'test_checks_are_exact_and_supported'),
            ('metadata_json JSON NULL', 'metadata_json VARCHAR(128) NULL', 'test_all_columns_types_and_nullability_match_specification'),
            ('source_key VARCHAR(128)', 'source_key VARCHAR(64)', 'test_all_columns_types_and_nullability_match_specification'),
        ]
        for before, after, method in mutations:
            with self.subTest(change=after):
                probe = CoreSchemaTests(method)
                probe.tables = parse(SQL.replace(before, after, 1))
                with self.assertRaises(AssertionError):
                    getattr(probe, method)()

    def test_documented_cleanup_is_exact_reverse_dependency_order(self):
        readme = (MIGRATIONS / 'README.md').read_text(encoding='utf-8')
        section = readme.split('<!-- cleanup-order -->')[1].split('<!-- /cleanup-order -->')[0]
        order = re.findall(r'^\d+\. `(m2_\w+)`', section, re.M)
        self.assertEqual(order, list(reversed(self.tables)))
        self.assertEqual(sorted(p.name for p in MIGRATIONS.glob('*.sql')),
                         ['0001_core_asset_identity.sql', '0002_market_current_history.sql',
                          '0003_market_units.sql'])


if __name__ == '__main__':
    unittest.main()
