"""Restricted, database-free DDL and SQL-three-valued CHECK model for 0003.

This is static contract evidence, not a MySQL parser or execution substitute.
Every DDL statement/clause and every modeled expression token must be consumed.
"""
import re
from test_core_schema_phase2 import IDENT, TYPE, names, split_sql


def parse_schema(sql):
    sql = re.sub(r'^\s*--[^\n]*$', '', sql, flags=re.M)
    statements = split_sql(sql, ';')
    if statements.pop() != '':
        raise ValueError('Missing final semicolon')
    tables, constraints = {}, set()
    for statement in statements:
        create = re.fullmatch(
            rf'CREATE TABLE ({IDENT})\s*\((.*)\) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci',
            statement, re.S)
        alter = re.fullmatch(rf'ALTER TABLE ({IDENT})\s+(.+)', statement, re.S)
        if create:
            table_name, body = create.groups()
            if table_name in tables:
                raise ValueError('Duplicate table')
            table = dict(columns={}, pk=None, indexes={}, fks={}, checks={})
            tables[table_name] = table
        elif alter:
            table_name, body = alter.groups()
            if table_name not in tables:
                raise ValueError('Unknown ALTER table')
            table = tables[table_name]
        else:
            raise ValueError('Unsupported DDL statement')
        for clause in split_sql(body, ','):
            modify = False
            if alter:
                drop = re.fullmatch(rf'DROP INDEX ({IDENT})', clause)
                if drop:
                    if drop[1] not in table['indexes']:
                        raise ValueError('Unknown DROP index')
                    del table['indexes'][drop[1]]
                    continue
                prefix = re.fullmatch(r'(ADD COLUMN|MODIFY COLUMN|ADD) (.+)', clause, re.S)
                if not prefix:
                    raise ValueError('Unsupported ALTER clause')
                modify = prefix[1] == 'MODIFY COLUMN'
                clause = prefix[2]
            col = re.fullmatch(
                rf"({IDENT}) ({TYPE})(?: COLLATE ({IDENT}))? (NOT NULL|NULL)( AUTO_INCREMENT)?(?: DEFAULT (''|1))?", clause)
            key = re.fullmatch(rf'(UNIQUE )?KEY ({IDENT}) \(([^()]+)\)', clause)
            pk = re.fullmatch(r'PRIMARY KEY \(([^()]+)\)', clause)
            fk = re.fullmatch(
                rf'CONSTRAINT ({IDENT}) FOREIGN KEY \(([^()]+)\) REFERENCES ({IDENT}) \(([^()]+)\) ON DELETE (RESTRICT|CASCADE|SET NULL)', clause)
            check = re.fullmatch(rf'CONSTRAINT ({IDENT}) CHECK \((.+)\)', clause, re.S)
            if modify and not col:
                raise ValueError('MODIFY must name a column')
            if col:
                field, datatype, collate, nullable, auto, default = col.groups()
                if (field in table['columns']) != modify:
                    raise ValueError('Duplicate or missing column')
                table['columns'][field] = (datatype, nullable == 'NULL', collate, bool(auto), default)
            elif pk:
                if table['pk'] is not None:
                    raise ValueError('Duplicate primary key')
                table['pk'] = names(pk[1])
            elif key:
                if key[2] in table['indexes']:
                    raise ValueError('Duplicate index')
                table['indexes'][key[2]] = (names(key[3]), bool(key[1]))
            elif fk or check:
                item = fk or check
                if item[1] in constraints:
                    raise ValueError('Duplicate constraint')
                constraints.add(item[1])
                if fk:
                    table['fks'][fk[1]] = (names(fk[2]), fk[3], names(fk[4]), fk[5])
                else:
                    table['checks'][check[1]] = check[2]
            else:
                raise ValueError('Unsupported definition: ' + clause)
    validate_references(tables)
    return tables


def validate_references(tables):
    for table in tables.values():
        keys = [table['pk']] + [v[0] for v in table['indexes'].values()]
        if not table['pk'] or any(not set(key) <= table['columns'].keys() for key in keys):
            raise ValueError('Missing key columns')
        for columns, parent, target, _ in table['fks'].values():
            if parent not in tables or len(columns) != len(target):
                raise ValueError('Invalid FK target')
            other = tables[parent]
            unique = [other['pk']] + [v[0] for v in other['indexes'].values() if v[1]]
            if target not in unique or not any(key[:len(columns)] == columns for key in keys):
                raise ValueError('Missing FK parent uniqueness or explicit support index')
            for child, dest in zip(columns, target):
                if child not in table['columns'] or dest not in other['columns']:
                    raise ValueError('Missing FK column')
                a, b = table['columns'][child], other['columns'][dest]
                if (a[0], a[2]) != (b[0], b[2]):
                    raise ValueError('Incompatible FK type/collation')


class CheckExpression:
    """Parse the 0003 expression subset; evaluate SQL UNKNOWN as None."""
    token = re.compile(r"\s*(<>|>=|<=|=|>|<|\(|\)|'[^']*'|[0-9]+|[a-zA-Z_][a-zA-Z_0-9]*)")

    def __init__(self, text):
        self.tokens, pos = [], 0
        while pos < len(text):
            match = self.token.match(text, pos)
            if not match:
                raise ValueError('Unsupported CHECK token')
            self.tokens.append(match[1])
            pos = match.end()
        self.pos = 0
        self.fields = set()
        self.tree = self.expression('OR')
        if self.pos != len(self.tokens):
            raise ValueError('Unconsumed CHECK tokens')

    def take(self, word):
        if self.pos < len(self.tokens) and self.tokens[self.pos] == word:
            self.pos += 1
            return True
        return False

    def expression(self, level):
        lower = (lambda: self.expression('AND')) if level == 'OR' else self.predicate
        tree = lower()
        while self.take(level):
            tree = (level, tree, lower())
        return tree

    def predicate(self):
        if self.take('('):
            tree = self.expression('OR')
            if not self.take(')'):
                raise ValueError('Unbalanced CHECK')
        else:
            if self.pos >= len(self.tokens):
                raise ValueError('Missing operand')
            value = self.tokens[self.pos]
            self.pos += 1
            if value.startswith("'"):
                tree = ('literal', value[1:-1])
            elif value.isdigit():
                tree = ('literal', int(value))
            elif re.fullmatch(IDENT, value):
                self.fields.add(value)
                tree = ('field', value)
            else:
                raise ValueError('Invalid operand')
        if self.take('IS'):
            negated = self.take('NOT')
            if self.take('NULL'):
                tree = ('notnull' if negated else 'null', tree)
            elif not negated and self.take('TRUE'):
                tree = ('true', tree)
            else:
                raise ValueError('Unsupported IS predicate')
        elif self.pos < len(self.tokens) and self.tokens[self.pos] in ('=', '<>', '>', '<', '>=', '<='):
            operator = self.tokens[self.pos]
            self.pos += 1
            tree = (operator, tree, self.predicate())
        return tree

    def evaluate(self, row):
        def evaluate(node):
            op = node[0]
            if op == 'literal':
                return node[1]
            if op == 'field':
                return row[node[1]]
            a = evaluate(node[1])
            if op in ('null', 'notnull', 'true'):
                return {'null': a is None, 'notnull': a is not None, 'true': a is True}[op]
            b = evaluate(node[2])
            if op == 'AND':
                return False if a is False or b is False else None if a is None or b is None else True
            if op == 'OR':
                return True if a is True or b is True else None if a is None or b is None else False
            if a is None or b is None:
                return None
            return {'=': lambda: a == b, '<>': lambda: a != b, '>': lambda: a > b,
                    '<': lambda: a < b, '>=': lambda: a >= b, '<=': lambda: a <= b}[op]()
        return evaluate(self.tree)


def foreign_keys_accept(table, row, catalog):
    """SQL MATCH SIMPLE: any NULL bypasses an FK (CHECKs must close holes)."""
    for columns, parent, target, _ in table['fks'].values():
        if parent != 'm2_units':
            continue
        values = tuple(row[column] for column in columns)
        if all(value is not None for value in values) and not any(
                tuple(unit[column] for column in target) == values for unit in catalog):
            return False
    return True
