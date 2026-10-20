"""Stored v2 facts -> Current plan. Reuses the existing writer's validation; no I/O to DB/provider."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.phase3n import writer_plan as writer

CORE = ('asset_id','source_id','route_id','currency','market_at','observed_at','price','bid','ask','volume')
UNITS = writer.UNIT_FIELDS


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def route_hash(route):
    return hashlib.sha256(json.dumps(route, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def qualified(fact, route, catalog):
    writer.observation.shared('identity', value=fact['id'])
    require(str(fact['observation_format_version']) == '2', 'current_requires_native_v2')
    payload = {k:fact[k] for k in CORE+UNITS}
    binding = {k:route[k] for k in ('id','asset_id','source_id','route_revision')+UNITS}
    key = bytes.fromhex(fact['dedupe_key'])
    planner = writer.WriterPlanner(catalog, [dict(format_version=2, route=binding)],
        [dict(format_version=2, payload=payload, dedupe_key=key)])
    result = planner.plan(payload, format_version=2, intent='NEW_NATIVE_V2', created_at=fact['created_at'])
    require(result['decision'] == 'DUPLICATE_UNCHANGED', 'stored_fact_invalid')
    return result['normalized'], result['canonical_bytes']


def projection(fact, normalized, route, now):
    result = {k:normalized[k] for k in ('asset_id','source_id','route_id','currency','price','bid','ask','market_at','observed_at')}
    result.update({k:normalized[k] for k in UNITS[:6]})
    result.update(day_open=None,day_high=None,day_low=None,previous_close=None,day_volume=None,
        day_volume_unit_key=None,day_volume_unit_version=None,updated_at=now,
        observation_id=str(fact['id']),observation_format_version='2',
        observation_dedupe_key=fact['dedupe_key'].upper(),route_revision=route['route_revision'])
    return result


def plan(data, catalog=None):
    catalog = catalog or writer.observation.catalog_module.normative_catalog()
    route, approval, now = data['route'], data['approval'], data['now']
    now = writer.observation.shared('timestamp', value=now)
    require(approval['route_sha256'] == route_hash(route), 'current_route_approval_drift')
    writer.observation.shared('timestamp', value=approval['approved_at'])
    require(route['route_type']=='quote' and route['priority']=='0', 'current_route_type')
    require(route['enabled']=='1' or (route['enabled']=='0' and approval.get('allow_disabled_projection') is True), 'current_route_not_approved')
    facts = data['facts'];require(type(facts) is list and len(facts)<=2, 'bounded_current_candidates')
    checked = [(f, *qualified(f, route, catalog)) for f in facts]
    checked.sort(key=lambda x:(x[1]['market_at'],x[1]['observed_at']), reverse=True)
    if len(checked)==2 and all(checked[0][1][k]==checked[1][1][k] for k in ('market_at','observed_at')):
        require(checked[0][2]==checked[1][2], 'current_equal_time_conflict')
    previous = data.get('current');old = data.get('current_fact')
    if previous is not None:
        require(old is not None and previous['observation_id']==str(old['id']), 'current_origin_missing')
        normalized, canonical = qualified(old, route, catalog)
        expected = projection(old, normalized, route, previous['updated_at'])
        require(previous==expected, 'current_projection_drift')
    if not checked:
        return dict(decision='UNCHANGED' if previous else 'MISSING', values=previous)
    fact, normalized, canonical = checked[0]
    if previous is not None:
        order = (normalized['market_at'],normalized['observed_at'])
        prior = (previous['market_at'],previous['observed_at'])
        if order < prior:
            return dict(decision='UNCHANGED_OLDER', values=previous)
        if order == prior:
            require(canonical==qualified(old,route,catalog)[1], 'current_equal_time_conflict')
            return dict(decision='UNCHANGED', values=previous)
    return dict(decision='UPDATE' if previous else 'INSERT', values=projection(fact,normalized,route,now))


if __name__ == '__main__':
    try:
        data=json.loads(sys.stdin.read())
        print(json.dumps(dict(ok=True,plans=[plan(item) for item in data['items']])))
    except (ValueError,KeyError,TypeError) as error:
        print(json.dumps(dict(ok=False,failure=str(error))))
