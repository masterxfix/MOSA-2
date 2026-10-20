"""Deterministic offline plans, explicit dispatch, immutable route snapshots.

No database, SQL executor, provider, clock, route creation or current/bar writer.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
from types import MappingProxyType

spec = importlib.util.spec_from_file_location('phase3n_observation', Path(__file__).with_name('observation_v2.py'))
observation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observation)
require = observation.require
UNIT_FIELDS = observation.UNIT_FIELDS


def checked_format(value):
    require(type(value) is int and value in (1, 2), 'explicit format version required')
    return value


def dispatch(version, route_version, intent, representation):
    version = checked_format(version)
    require(version == route_version, 'route/observation format mismatch')
    require(intent == {1: 'V1_REPLAY', 2: 'NEW_NATIVE_V2'}[version], 'format/intent mismatch')
    require(representation == 'native', 'derived projection is not native history')
    return version


def fact_identity(row):
    # A new physical route or domain is not authority to reimport an old fact.
    return tuple(row[f] for f in ('asset_id','source_id','market_at','observed_at'))


class WriterPlanner:
    def __init__(self, catalog, routes, existing=()):
        self.catalog = catalog
        self._routes = {}
        for envelope in copy.deepcopy(routes):
            require(type(envelope) is dict, 'route envelope')
            require(set(envelope) == {'format_version','route'}, 'route envelope fields')
            version = checked_format(envelope['format_version'])
            row = envelope['route']
            require(type(row) is dict, 'route record')
            require(set(row) == {'id','asset_id','source_id','route_revision'} | set(UNIT_FIELDS), 'route fields')
            for field in ('id','asset_id','source_id'):
                row[field] = observation.shared('identity', value=row[field])
            row['route_revision'] = observation.units.integer(row['route_revision'], 4294967295)
            if version == 1:
                require(all(row[f] is None for f in UNIT_FIELDS), 'unit-aware route cannot use v1')
            else:
                semantic, _ = observation.binding(row, catalog)
                row.update(semantic)
            require(row['id'] not in self._routes, 'physical route revision is immutable')
            self._routes[row['id']] = (version, MappingProxyType(row))
        self._routes = MappingProxyType(self._routes)
        self._existing = copy.deepcopy(tuple(existing))
        keys = set()
        for old in self._existing:
            require(set(old) == {'format_version','payload','dedupe_key'}, 'existing snapshot fields')
            checked_format(old['format_version'])
            require(type(old['dedupe_key']) is bytes and len(old['dedupe_key']) == 32, 'raw stored dedupe key')
            require(old['dedupe_key'] not in keys, 'duplicate stored dedupe key')
            keys.add(old['dedupe_key'])

    def plan(self, raw, *, format_version, intent, created_at, representation='native'):
        try:
            version = checked_format(format_version)
            require(type(raw) is dict and 'route_id' in raw, 'observation fields')
            route_id = observation.shared('identity', value=raw['route_id'])
            require(route_id in self._routes, 'unknown route')
            route_version, route = self._routes[route_id]
            dispatch(version, route_version, intent, representation)
            if version == 1:
                legacy = observation.shared('legacy', row=raw)
                row, canonical = legacy['row'], legacy['canonical'].encode('utf-8')
            else:
                row = observation.normalize_observation(raw, self.catalog)
                canonical = observation._canonical(row)
            for field in ('asset_id','source_id'):
                require(row[field] == route[field], 'route identity mismatch')
            if version == 2:
                require(all(row[f] == route[f] for f in UNIT_FIELDS), 'route unit binding mismatch')
            key = hashlib.sha256(canonical).digest()
            marker = None if version == 1 else 2  # Legacy SQL marker remains NULL.
            payload = dict(row, observation_format_version=marker)
            result = {'decision':'INSERT', 'observation_format_version':marker,
                      'normalized':row, 'canonical_bytes':canonical, 'dedupe_key':key,
                      'expected_db_columns':tuple(payload)+('dedupe_key','created_at'),
                      'catalog_fingerprint':self.catalog.fingerprint if version == 2 else None,
                      'route_binding':{'route_id':route_id, 'route_revision':route['route_revision'],
                                       'format_version':version, 'matched_fields':dict(route)}}
            for old in self._existing:
                if old['dedupe_key'] == key:
                    result['decision'] = ('DUPLICATE_UNCHANGED' if old['format_version'] == version
                                          and old['payload'] == row else 'CONFLICT')
                    return result
            for old in self._existing:
                if old['format_version'] == 1:
                    stored = observation.shared('legacy', row=old['payload'])
                    prior = stored['row']
                    prior_key = hashlib.sha256(stored['canonical'].encode()).digest()
                else:
                    prior = observation.normalize_observation(old['payload'], self.catalog)
                    prior_key = hashlib.sha256(observation._canonical(prior)).digest()
                require(prior_key == old['dedupe_key'], 'existing snapshot hash mismatch')
                if prior['route_id'] in self._routes:
                    prior_version, prior_route = self._routes[prior['route_id']]
                    require(prior_version == old['format_version'], 'physical route format changed')
                    require(all(prior[f] == prior_route[f] for f in ('asset_id','source_id')),
                            'physical route identity changed')
                    if prior_version == 2:
                        require(all(prior[f] == prior_route[f] for f in UNIT_FIELDS),
                                'physical route unit revision changed')
                require(fact_identity(prior) != fact_identity(row), 'existing fact cannot change route/domain')
            require(version == 2, 'v1 is replay-only; no new legacy insert')
            created_at = observation.shared('timestamp', value=created_at)
            values = dict(payload, dedupe_key=key, created_at=created_at)
            result['expected_db_columns'] = tuple(values)
            result['db_values'] = values
            return result
        except (ValueError, KeyError, TypeError) as error:
            return {'decision':'REJECT', 'reason':str(error)}
