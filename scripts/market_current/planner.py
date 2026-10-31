"""Stored v2 facts -> Current plan. Reuses the existing writer's validation; no I/O to DB/provider."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess

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


def select(facts, route, now, previous=None, catalog=None):
    """Shared PHP contract, also called directly by the read-only Observations view."""
    catalog = catalog or writer.observation.catalog_module.normative_catalog()
    units = {}
    for key, version in (('quote_unit_key', 'quote_unit_version'),
                         ('quantity_basis_unit_key', 'quantity_basis_unit_version'),
                         ('volume_unit_key', 'volume_unit_version')):
        if route[key] is not None:
            value = catalog.resolve(route[key], route[version], route['unit_contract_version'])
            units[(value['unit_key'], value['unit_version'])] = value
    request = dict(facts=facts, route=route, now=now, previous=previous, units=list(units.values()))
    process = subprocess.run(['php', str(Path(__file__).with_name('selection.php'))],
        input=json.dumps(request), capture_output=True, text=True, timeout=10)
    require(process.returncode == 0 and not process.stderr, 'quote_selection_process')
    reply = json.loads(process.stdout)
    require(reply['ok'], reply.get('failure', 'quote_selection_failure'))
    return reply['result']


def check_approval(route, approval):
    require(approval['route_sha256'] == route_hash(route), 'current_route_approval_drift')
    writer.observation.shared('timestamp', value=approval['approved_at'])
    require(route['route_type']=='quote' and route['priority']=='0', 'current_route_type')
    require(route['enabled']=='1' or (route['enabled']=='0' and approval.get('allow_disabled_projection') is True), 'current_route_not_approved')


def changing_route(data):
    previous = data.get('current')
    return previous is not None and previous['route_id'] != data['route']['id']


def previous_route(data):
    """A source change never reinterprets the old fact with the new route."""
    route = data.get('current_route')
    require(type(route) is dict, 'current_previous_route_missing')
    previous = data['current']
    require(route['id'] == previous['route_id'] and route['source_id'] == previous['source_id'],
            'current_previous_route_binding')
    require(route['asset_id'] == previous['asset_id'] == data['route']['asset_id'],
            'current_transition_asset')
    require(all(route[key] == data['route'][key] for key in UNITS),
            'current_transition_units')
    return route


def check_route_transition(data):
    if not changing_route(data):
        return
    approval = data['approval']
    require(approval.get('allow_route_transition') is True, 'current_transition_not_approved')
    old_route = previous_route(data)
    require(approval.get('previous_route_sha256') == route_hash(old_route),
            'current_transition_approval_drift')


def plan_facts(data, catalog=None):
    """Pure projection plan; caller must keep approval checking separate from inspection."""
    catalog = catalog or writer.observation.catalog_module.normative_catalog()
    route = data['route']
    now = writer.observation.shared('timestamp', value=data['now'])
    facts = data['facts'];require(type(facts) is list and len(facts)<=2, 'bounded_current_candidates')
    for fact in facts:
        qualified(fact, route, catalog)
    previous = data.get('current');old = data.get('current_fact')
    transition = changing_route(data)
    if previous is not None:
        require(old is not None and previous['observation_id']==str(old['id']), 'current_origin_missing')
        old_route = previous_route(data) if transition else route
        normalized, canonical = qualified(old, old_route, catalog)
        expected = projection(old, normalized, old_route, previous['updated_at'])
        require(previous==expected, 'current_projection_drift')
    if transition:
        # Validate each source independently with the unchanged PHP selection
        # contract. Quotes from different venues may legitimately differ.
        select([], old_route, now, old, catalog)
        selected = select(facts, route, now, None, catalog)
        if selected['decision'] == 'MISSING':
            return dict(decision='UNCHANGED', values=previous)
        fact = selected['fact']
        new_time = (fact['market_at'], fact['observed_at'])
        old_time = (old['market_at'], old['observed_at'])
        if new_time <= old_time:
            return dict(decision='UNCHANGED_OLDER' if new_time < old_time else 'UNCHANGED',
                        values=previous)
        return dict(decision='UPDATE', values=projection(fact, fact, route, now))
    selected = select(facts, route, now, old if previous is not None else None, catalog)
    if selected['decision'] not in ('INSERT', 'UPDATE'):
        return dict(decision=selected['decision'], values=previous)
    fact = selected['fact']
    return dict(decision=selected['decision'], values=projection(fact, fact, route, now))


def plan(data, catalog=None):
    # The write path still requires exactly the original explicit approval checks.
    check_approval(data['route'], data['approval'])
    check_route_transition(data)
    return plan_facts(data, catalog)


if __name__ == '__main__':
    try:
        data=json.loads(sys.stdin.read())
        print(json.dumps(dict(ok=True,plans=[plan(item) for item in data['items']])))
    except (ValueError,KeyError,TypeError) as error:
        print(json.dumps(dict(ok=False,failure=str(error))))
