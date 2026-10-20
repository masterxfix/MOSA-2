"""Offline Phase-3M plan/readback/replay, using the unchanged Phase-3L contract."""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('phase3l_units', ROOT / 'scripts/phase3l/unit_seed.py')
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)
APPROVED = 'b66df6f972ad13c05c3f34c604088c0281dcd9f0ff4bafad45b9600aa2b747ee'
MANIFEST_BYTES = '0d9f196e4ccbd5e687292fa3d7a1a087b343ec81fb609b8b64b6454713246bbf'
DB_FIELDS = seed.FIELDS + ('definition_sha256', 'created_at')


def load_approved(path=seed.DEFAULT):
    raw = Path(path).read_bytes()
    seed.require(hashlib.sha256(raw).hexdigest() == MANIFEST_BYTES, 'manifest bytes changed')
    manifest = seed.load_manifest(path)
    seed.require(seed.package_sha256(manifest) == APPROVED, 'unapproved package')
    seed.require(len(manifest['definitions']) == 4, 'four definitions required')
    return manifest


def timestamp(value):
    seed.require(type(value) is str and re.fullmatch(
        r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}', value) is not None,
        'frozen UTC DATETIME(6) required')
    parsed = datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
    seed.require(parsed.year >= 1000, 'DATETIME year outside SQL range')
    return value


def insert_plan(manifest):
    seed.require(seed.package_sha256(manifest) == APPROVED, 'unapproved package')
    definitions = seed.validate_manifest(manifest)
    # No execution and no clock: created_at is frozen once AFTER the live FK probe.
    base = seed.normalize_definition(definitions[0])
    base.update(unit_key='SEED_PROBE_BASE', base_unit_key='SEED_PROBE_BASE', unit_version='1',
                base_unit_version='1', scale_numerator='1', scale_denominator='1')
    minor = dict(base, unit_key='SEED_PROBE_MINOR', scale_denominator='100')
    probes = [{**r, 'definition_sha256': seed.definition_sha256(r)} for r in (base, minor)]
    return {'plan_format': 'mosa2-unit-insert-plan-v1', 'package_sha256': APPROVED,
            'manifest_sha256': MANIFEST_BYTES,
            'definitions': definitions,
            'canonical_definitions': [seed.canonical_definition(row).decode('utf-8') for row in definitions],
            'manifest': manifest, 'synthetic_probe': probes}


def resolve_plan(manifest, created_at):
    plan = insert_plan(manifest)
    timestamp(created_at)
    plan['created_at'] = created_at
    plan['rows'] = [{**{field: row[field] for field in seed.FIELDS},
                     'definition_sha256': row['definition_sha256'], 'created_at': created_at}
                    for row in plan['definitions']]
    return plan


def normalize_readback(raw):
    seed.require(type(raw) is dict and set(raw) == set(DB_FIELDS), 'DB readback fields')
    row = seed.normalize_definition(raw)
    digest = raw['definition_sha256']
    if type(digest) is bytes:
        seed.require(len(digest) == 32, 'binary definition hash length')
        digest = digest.hex()
    seed.require(type(digest) is str and re.fullmatch(r'[a-f0-9]{64}', digest) is not None,
                 'lowercase hex definition hash required')
    seed.require(seed.definition_sha256(row) == digest, 'DB definition hash mismatch')
    return {**row, 'definition_sha256': digest, 'created_at': timestamp(raw['created_at'])}


def replay_plan(manifest, existing, created_at):
    """Classifies only. A conflict raises; never repairs or executes an insert."""
    expected = resolve_plan(manifest, created_at)['rows']
    seed.require(type(existing) is list, 'DB rows required')
    indexed = {}
    for raw in existing:
        row = normalize_readback(raw)
        identity = seed.identity(row)
        seed.require(identity not in indexed, 'duplicate DB identity')
        indexed[identity] = row
    seed.require(set(indexed) <= {seed.identity(row) for row in expected}, 'unexpected DB unit')
    result = {'duplicates': 0, 'inserts': 0, 'updates': 0, 'conflicts': 0, 'rows': []}
    for row in expected:
        current = indexed.get(seed.identity(row))
        if current is None:
            result['inserts'] += 1
            classification = 'missing / would insert'
        else:
            seed.require(current == row, 'CONFLICT: existing unit differs')
            result['duplicates'] += 1
            classification = 'duplicate / unchanged'
        result['rows'].append({'unit_key': row['unit_key'], 'unit_version': row['unit_version'],
                               'classification': classification})
    return result


def verify_readback(manifest, existing, created_at):
    replay = replay_plan(manifest, existing, created_at)
    seed.require((replay['duplicates'], replay['inserts']) == (4, 0), 'readback must contain exactly four units')
    references = {seed.identity(row): row['definition_reference'] for row in manifest['definitions']}
    # created_at is insert metadata; do not add it to the approved public package.
    # Evidence is nonpersisted: restore it from the approved manifest by identity.
    restored = []
    for raw in existing:
        row = normalize_readback(raw)
        del row['created_at']
        row['definition_reference'] = references[seed.identity(row)]
        restored.append(row)
    reconstructed = dict(manifest, definitions=restored)
    seed.require(seed.package_sha256(reconstructed) == APPROVED, 'DB package mismatch')
    return {'package_sha256': APPROVED, 'unit_rows': 4, 'replay': replay}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=seed.DEFAULT)
    parser.add_argument('--readback', type=Path)
    parser.add_argument('--created-at')
    parser.add_argument('--transport', type=Path, help='Write secret-free validated transport, never SQL')
    args = parser.parse_args()
    manifest = load_approved(args.manifest)
    plan = insert_plan(manifest)
    if args.readback:
        seed.require(args.created_at is not None, 'frozen created_at required for readback')
        result = verify_readback(manifest, json.loads(args.readback.read_text(encoding='utf-8'),
                                  object_pairs_hook=seed.unique_object), args.created_at)
    else:
        result = {'package_sha256': APPROVED,
                  'insert_order': [r['unit_key'] + '@' + r['unit_version'] for r in plan['definitions']],
                  'definition_hashes': [r['definition_sha256'] for r in plan['definitions']]}
    if args.transport:
        with args.transport.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(seed.compact(plan) + '\n')
    print(seed.compact(result))


if __name__ == '__main__':
    main()
