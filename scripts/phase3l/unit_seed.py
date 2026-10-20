"""Provider-neutral, database-free unit definitions. No third-party dependencies."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import re

CONTRACT = 'mosa2-market-unit-v1'
FORMAT = 'mosa2-unit-seed-manifest-v1'
DOMAIN = 'mosa2-unit-definition-v1'
PACKAGE_DOMAIN = 'mosa2-unit-package-v1'
FIELDS = ('unit_key', 'unit_version', 'unit_contract_version', 'dimension_key',
          'base_unit_key', 'base_unit_version', 'monetary_currency_code',
          'scale_numerator', 'scale_denominator', 'status')
EXTRA = {'definition_sha256', 'definition_reference', 'created_at'}
DEFAULT = Path(__file__).resolve().parents[2] / 'docs/database/seeds/0001_market_units_v1.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, maximum):
    require(type(value) in (int, str), 'integer required; no floats/bools')
    text = str(value)
    require(re.fullmatch(r'[1-9][0-9]*', text) is not None, 'positive canonical integer required')
    require(len(text) <= len(str(maximum)) and int(text) <= maximum, 'integer exceeds SQL range')
    return text


def key(value, pattern):
    require(type(value) is str and re.fullmatch(pattern, value) is not None, 'canonical ASCII key required')
    return value


def normalize_definition(raw):
    require(type(raw) is dict and set(FIELDS) <= raw.keys() <= set(FIELDS) | EXTRA,
            'missing or unknown definition field')
    row = {field: raw[field] for field in FIELDS}
    for field in ('unit_key', 'base_unit_key'):
        row[field] = key(row[field], r'[A-Z][A-Z0-9_]{0,63}')
    row['dimension_key'] = key(row['dimension_key'], r'[a-z][a-z0-9_]{0,63}')
    for field in ('unit_version', 'base_unit_version'):
        row[field] = integer(row[field], 4294967295)
    for field in ('scale_numerator', 'scale_denominator'):
        row[field] = integer(row[field], 10**38 - 1)
    require(row['unit_contract_version'] == CONTRACT, 'unsupported unit contract')
    require(row['status'] == 'frozen', 'status must be frozen')
    if row['dimension_key'] == 'monetary':
        key(row['monetary_currency_code'], r'[A-Z]{3}')
        require(row['monetary_currency_code'] != 'XXX', 'pseudo currency forbidden')
    else:
        require(row['monetary_currency_code'] is None, 'non-monetary currency must be null')
    require(math.gcd(int(row['scale_numerator']), int(row['scale_denominator'])) == 1,
            'factor must be reduced')
    if 'created_at' in raw:
        timestamp = raw['created_at']
        require(type(timestamp) is str and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}', timestamp) is not None,
                'created_at must be a frozen UTC DATETIME(6) string')
        datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f')
    return row


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def canonical_definition(raw):
    return (DOMAIN + '\n' + compact(normalize_definition(raw))).encode('utf-8')


def definition_sha256(raw):
    return hashlib.sha256(canonical_definition(raw)).hexdigest()


def identity(row):
    return row['unit_key'], row['unit_version']


def base_identity(row):
    return row['base_unit_key'], row['base_unit_version']


def validate_definitions(definitions):
    require(type(definitions) is list and bool(definitions), 'nonempty definitions required')
    rows = []
    catalog = {}
    for raw in definitions:
        row = normalize_definition(raw)
        require(identity(row) not in catalog, 'duplicate unit/version')
        require(type(raw.get('definition_reference')) is str and bool(raw['definition_reference'].strip()),
                'definition evidence required')
        digest = definition_sha256(row)
        require(raw.get('definition_sha256') == digest, 'definition hash mismatch')
        row['definition_sha256'] = digest
        row['definition_reference'] = raw['definition_reference']
        if 'created_at' in raw:
            row['created_at'] = raw['created_at']
        catalog[identity(row)] = row
        rows.append(row)
    for row in rows:
        require(base_identity(row) in catalog, 'missing base')
        base = catalog[base_identity(row)]
        require(base_identity(base) == identity(base), 'chains/cycles forbidden')
        require(row['dimension_key'] == base['dimension_key'], 'dimension mismatch')
        require(row['monetary_currency_code'] == base['monetary_currency_code'], 'currency mismatch')
        if identity(row) == base_identity(row):
            require(row['scale_numerator'] == row['scale_denominator'] == '1', 'self base must be 1/1')
    # Bases first, then dependents; ASCII key and numeric version break ties.
    return sorted(rows, key=lambda r: (identity(r) != base_identity(r), r['unit_key'], int(r['unit_version'])))


def package_sha256(manifest):
    require(type(manifest) is dict and manifest.get('manifest_format') == FORMAT, 'unsupported manifest')
    require(set(manifest) == {'manifest_format', 'package_key', 'package_version',
                             'unit_contract_version', 'definitions', 'package_sha256'}, 'manifest fields')
    require(manifest['unit_contract_version'] == CONTRACT, 'package contract mismatch')
    payload = {'manifest_format': FORMAT,
               'package_key': key(manifest['package_key'], r'[a-z][a-z0-9_-]{0,63}'),
               'package_version': integer(manifest['package_version'], 4294967295),
               'unit_contract_version': CONTRACT,
               'definitions': validate_definitions(manifest['definitions'])}
    return hashlib.sha256((PACKAGE_DOMAIN + '\n' + compact(payload)).encode('utf-8')).hexdigest()


def validate_manifest(manifest):
    require(manifest.get('package_sha256') == package_sha256(manifest), 'package fingerprint mismatch')
    return validate_definitions(manifest['definitions'])


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, 'duplicate JSON member')
        result[name] = value
    return result


def load_manifest(path=DEFAULT):
    manifest = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    validate_manifest(manifest)
    return manifest


def project_exact(native, definition, scale=8):
    """Synthetic decimal projection, exact or fail; never changes the native input."""
    row = normalize_definition(definition)
    require(type(native) is str and re.fullmatch(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?', native) is not None,
            'native decimal string required')
    require(type(scale) is int and 0 <= scale <= 8, 'output scale must be 0..8')
    unsigned = native.lstrip('-')
    parts = unsigned.split('.')
    require(len(parts[0]) <= 24 and (len(parts) == 1 or len(parts[1]) <= 8), 'native DECIMAL(32,8) range')
    value = Fraction(native) * Fraction(int(row['scale_numerator']), int(row['scale_denominator']))
    scaled = value * 10**scale
    require(scaled.denominator == 1 and abs(value) < 10**24, 'normalization_unrepresentable')
    digits = str(abs(scaled.numerator)).zfill(scale + 1)
    text = digits if scale == 0 else (digits[:-scale] + '.' + digits[-scale:]).rstrip('0').rstrip('.')
    return ('-' if scaled < 0 else '') + text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', nargs='?', default=DEFAULT, type=Path)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    print(compact({'package_sha256': manifest['package_sha256'],
                   'insert_order': [r['unit_key'] + '@' + r['unit_version']
                                    for r in validate_manifest(manifest)]}))


if __name__ == '__main__':
    main()
