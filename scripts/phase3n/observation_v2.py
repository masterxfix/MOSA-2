"""Observation-v2 normalization/canonical bytes; local PHP reuses v1 primitives."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('phase3n_catalog', HERE/'unit_catalog_adapter.py')
catalog_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog_module)
units = catalog_module.units
require = units.require
V1_FIELDS = ('asset_id','source_id','route_id','currency','market_at','observed_at','price','bid','ask','volume')
UNIT_FIELDS = ('unit_contract_version','quote_unit_key','quote_unit_version',
               'quantity_basis_unit_key','quantity_basis_unit_version','quantity_basis_amount',
               'volume_unit_key','volume_unit_version')
FIELDS = V1_FIELDS + UNIT_FIELDS
DOMAIN = b'mosa2-observation-v2\n'


def shared(operation, **arguments):
    process = subprocess.run(['php', str(HERE/'value_adapter.php')],
                             input=units.compact(dict(operation=operation, **arguments)).encode('utf-8'),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    stdout = process.stdout.decode('utf-8', 'strict')
    stderr = process.stderr.decode('utf-8', 'strict')
    require(process.returncode == 0, 'value adapter process failed')
    require(not stderr, 'value adapter diagnostics')
    result = json.loads(stdout)
    require(result['ok'], result.get('reason', 'value adapter failed'))
    return result['result']


def binding(raw, catalog):
    require(raw['unit_contract_version'] == units.CONTRACT, 'unsupported unit contract')
    result = {'unit_contract_version': units.CONTRACT}
    quote = catalog.resolve(raw['quote_unit_key'], raw['quote_unit_version'], units.CONTRACT)
    result.update(quote_unit_key=quote['unit_key'], quote_unit_version=quote['unit_version'])
    triple = [raw[k] for k in UNIT_FIELDS[3:6]]
    require(all(v is None for v in triple) or all(v is not None for v in triple), 'quantity triple')
    result.update(zip(UNIT_FIELDS[3:6], [None]*3))
    if triple[0] is not None:
        basis = catalog.resolve(triple[0], triple[1], units.CONTRACT)
        amount = triple[2]
        require(type(amount) is str and re.fullmatch(r'(0|[1-9][0-9]*)(\.[0-9]+)?', amount) is not None,
                'canonical quantity decimal string')
        parts = amount.split('.')
        require(len(parts[0]) <= 24 and (len(parts) == 1 or len(parts[1]) <= 8), 'quantity precision')
        amount = parts[0]+'.'+(parts[1] if len(parts) == 2 else '').ljust(8, '0')
        require(any(c in '123456789' for c in amount), 'quantity must be positive')
        result.update(quantity_basis_unit_key=basis['unit_key'], quantity_basis_unit_version=basis['unit_version'],
                      quantity_basis_amount=amount)
    key, version = raw['volume_unit_key'], raw['volume_unit_version']
    require((key is None) == (version is None), 'volume pair')
    result.update(volume_unit_key=None, volume_unit_version=None)
    if key is not None:
        volume = catalog.resolve(key, version, units.CONTRACT)
        result.update(volume_unit_key=volume['unit_key'], volume_unit_version=volume['unit_version'])
    return result, quote


def normalize_observation(raw, catalog):
    require(type(raw) is dict and set(raw) == set(FIELDS), 'v2 observation fields')
    core = shared('values', row={f: raw[f] for f in V1_FIELDS})
    semantic, quote = binding(raw, catalog)
    require(core['currency'] == quote['monetary_currency_code'], 'quote currency mismatch')
    require((core['volume'] is None) == (semantic['volume_unit_key'] is None), 'volume/unit mismatch')
    return dict(core, **semantic)


def _canonical(normalized):
    return DOMAIN + units.compact({f: normalized[f] for f in FIELDS}).encode('utf-8')


def canonical_observation(raw, catalog):
    return _canonical(normalize_observation(raw, catalog))


def dedupe_key(raw, catalog):
    return hashlib.sha256(canonical_observation(raw, catalog)).digest()
