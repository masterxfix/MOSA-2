"""Pinned offline catalog; validation and exact projection belong to Phase 3L."""
import copy
import hashlib
import importlib.util
from pathlib import Path
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('phase3n_unit_contract', ROOT/'scripts/phase3l/unit_seed.py')
units = importlib.util.module_from_spec(spec)
spec.loader.exec_module(units)
APPROVED = 'b66df6f972ad13c05c3f34c604088c0281dcd9f0ff4bafad45b9600aa2b747ee'
RUNTIME_APPROVED = 'd04ad8778bc2bf61acb6056335b765b34364117c1f0f0edc9efdb36cd1eb82bc'
MANIFEST_BYTES = '0d9f196e4ccbd5e687292fa3d7a1a087b343ec81fb609b8b64b6454713246bbf'


class UnitCatalog:
    """The approval anchor is supplied by trusted policy, never by the manifest.

    A different fingerprint is an explicit offline qualification (e.g. synthetic
    quantity fixtures), not authority to use that package in a later live writer.
    """
    def __init__(self, manifest, expected_fingerprint):
        rows = units.validate_manifest(copy.deepcopy(manifest))
        units.require(manifest['package_sha256'] == expected_fingerprint, 'unapproved unit package')
        self._fingerprint = expected_fingerprint
        self._rows = MappingProxyType({units.identity(r): MappingProxyType(r) for r in rows})

    @property
    def fingerprint(self):
        return self._fingerprint

    def resolve(self, key, version, contract):
        units.key(key, r'[A-Z][A-Z0-9_]{0,63}')
        version = units.integer(version, 4294967295)
        units.require(contract == units.CONTRACT, 'unsupported unit contract')
        units.require((key, version) in self._rows, 'unknown unit/version')
        return dict(self._rows[(key, version)])

    def project(self, native, key, version, scale=8):
        return units.project_exact(native, self.resolve(key, version, units.CONTRACT), scale)


def normative_catalog():
    units.require(hashlib.sha256(units.DEFAULT.read_bytes()).hexdigest() == MANIFEST_BYTES,
                  'normative manifest bytes changed')
    return UnitCatalog(units.load_manifest(), APPROVED)


def runtime_catalog():
    original = units.load_manifest()
    units.require(hashlib.sha256(units.DEFAULT.read_bytes()).hexdigest() == MANIFEST_BYTES
                  and original['package_sha256'] == APPROVED, 'unapproved original unit package')
    path = ROOT/'api/market_core/native_currency_units.json'
    units.require(hashlib.sha256(path.read_bytes()).hexdigest() == 'd170bc53909e6d38daf19682b6a9a454ee53653fa4a3885243662915ad924da6',
                  'native currency manifest bytes changed')
    additional = units.load_manifest(path)
    combined = dict(original, package_key='market-units-with-native-currencies-v1',
                    definitions=original['definitions'] + additional['definitions'])
    combined['package_sha256'] = units.package_sha256(combined)
    return UnitCatalog(combined, RUNTIME_APPROVED)
