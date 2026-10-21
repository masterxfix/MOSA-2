"""Read-only comparison with an immutable historical plan; never grants authority."""
import copy
from pathlib import Path
from scripts.market_current import planner, preview, takeover


def compare(plan, snapshot):
    scope = preview.php(dict(operation='scope'), Path(__file__).with_name('preview_read.php'))['scope']
    expected = plan['items']; actual = snapshot['items']
    planner.require(len(expected) == len(actual) == 5, 'reconcile_scope')
    planner.require({x['reference']['isin'] for x in expected} == set(scope), 'reconcile_plan_scope')
    planner.require({x['isin'] for x in actual} == set(scope), 'reconcile_actual_scope')
    planner.require(len({x['isin'] for x in actual}) == 5, 'reconcile_duplicate')
    by_isin = {x['isin']: x for x in actual}; reports = []
    catalog = planner.writer.observation.catalog_module.normative_catalog()
    for item in expected:
        original = item['reference']; entry = by_isin[original['isin']]
        result = dict(name=scope[original['isin']], state='UNVERIFIABLE', current_status='UNKNOWN',
            provenance='NOT_VERIFIED', routes='NOT_VERIFIED', binding='NOT_VERIFIED', observations='NOT_VERIFIED')
        try:
            planner.require(entry['name'] == original['name'] == result['name'], 'reconcile_name')
            data = preview.php(entry, Path(__file__).with_name('preview_read.php'))['input']
            planner.require(data['now'] == snapshot['as_of'], 'reconcile_clock')
            before = original['input']; route = data['route']; current = data.get('current')
            result['current_status'] = 'PRESENT' if current is not None else 'MISSING'
            result['routes'] = 'UNCHANGED' if route == before['route'] and planner.route_hash(route) == item['route_sha256'] else 'CHANGED'
            result['binding'] = 'UNCHANGED' if entry['scope_rows'] == original['scope_rows'] else 'CHANGED'
            result['observations'] = 'UNCHANGED' if data['facts'] == before['facts'] else 'CHANGED'
            # The original origin can cease to be returned once Current points to the target.
            # Check it whenever it remains the current origin; never claim a full-table proof.
            origin_same = current is None or data.get('current_fact') == before.get('current_fact')
            for fact in data['facts']:
                planner.qualified(fact, route, catalog)
            planner.plan_facts(data, catalog)  # Existing exact projection/provenance/clock/dedupe checks.
            if current is not None:
                planner.writer.observation.shared('timestamp', value=current['updated_at'])
            result['provenance'] = 'VALID' if current is not None else 'NOT_APPLICABLE_CURRENT_MISSING'
            target_facts = [f for f in before['facts'] if f['id'] == item['observation_id']]
            planner.require(len(target_facts) == 1, 'reconcile_target_fact')
            fact = target_facts[0]
            normalized, _ = planner.qualified(fact, before['route'], catalog)
            target = None if current is None else planner.projection(fact, normalized, before['route'], current['updated_at'])
            if current == before.get('current') and origin_same:
                result['state'] = 'ORIGINAL'
            elif current is not None and current == target and data['current_fact'] == fact and plan['as_of'] <= current['updated_at'] <= snapshot['as_of']:
                result['state'] = 'TARGET'
            else:
                result['state'] = 'DIFFERENT'
            # Raw values/IDs/times remain in this private return object, not the public summary.
            result['private_current'] = copy.deepcopy(current)
        except (ValueError, KeyError, TypeError):
            result['state'] = 'UNVERIFIABLE'
        reports.append(result)
    states = [r['state'] for r in reports]
    unchanged = all(r[k] == 'UNCHANGED' for r in reports for k in ('routes', 'binding', 'observations'))
    if 'UNVERIFIABLE' in states:
        classification = 'D'
    elif unchanged and states == ['TARGET'] * 5:
        classification = 'A'
    elif unchanged and states == ['ORIGINAL'] * 5:
        classification = 'B'
    else:
        classification = 'C'
    return dict(classification=classification, reports=reports,
        other_tables='NOT_VERIFIABLE_NO_COMPLETE_BASELINE',
        baseline_scope='FIVE_ROUTES_BINDINGS_CANDIDATE_FACTS_AND_CURRENT_ORIGINS_ONLY')


def public_summary(report):
    keys = ('name', 'state', 'current_status', 'provenance', 'routes', 'binding', 'observations')
    return dict(classification=report['classification'], reports=[{k: r[k] for k in keys} for r in report['reports']],
        other_tables=report['other_tables'], baseline_scope=report['baseline_scope'],
        read_only_confirmed=True, business_writes=0, provider_requests=0)
