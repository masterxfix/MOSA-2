"""Private read-only Current preview; uses the existing planner, never executes a plan."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.market_current import planner

REASONS = dict(INSERT='CURRENT_MISSING', UPDATE='NEWER_MARKET_OR_OBSERVATION_TIME',
               UNCHANGED='CURRENT_ALREADY_CURRENT_OR_NO_CANDIDATES',
               UNCHANGED_OLDER='OLDER_MARKET_OR_OBSERVATION_TIME', MISSING='NO_NATIVE_V2_FACT')


def php(request, path):
    p = subprocess.run(['php', str(path)], input=json.dumps(request), text=True,
                       capture_output=True, timeout=15)
    planner.require(p.returncode == 0 and not p.stderr, 'preview_php_process')
    reply = json.loads(p.stdout)
    planner.require(reply.get('ok') is True, reply.get('failure', 'preview_php_failed'))
    return reply


def describe(value, now):
    if value is None:
        return None
    result = {key: value[key] for key in ('price', 'currency', 'quote_unit_key', 'quote_unit_version',
              'quantity_basis_unit_key', 'quantity_basis_unit_version', 'quantity_basis_amount', 'market_at', 'observed_at')}
    result['observation_id'] = value.get('observation_id', value.get('id'))
    result['age_seconds'] = php(dict(operation='describe', row=value, now=now), Path(__file__).with_name('preview_read.php'))['age_seconds']
    result['verified'] = True
    return result


def preview(data, catalog=None):
    """Approval absence is a finding, never authority to synthesize an approval."""
    report = dict(decision='BLOCKED', reason='VALIDATION_FAILED', required_approvals=[],
                  previous_current=None, latest_observation=None, candidate_projection=None,
                  candidate_decision=None, business_writes=0)
    if isinstance(data.get('current'), dict):
        report['previous_current'] = {key: data['current'].get(key) for key in
            ('price', 'currency', 'quote_unit_key', 'market_at', 'observed_at', 'observation_id')}
        report['previous_current']['verified'] = False
    try:
        route, now = data['route'], data['now']
        planner.require(type(data['facts']) is list and len(data['facts']) <= 2, 'bounded_current_candidates')
        # The existing v2 writer remains the validator for every supplied fact.
        catalog = catalog or planner.writer.observation.catalog_module.normative_catalog()
        for fact in data['facts']:
            planner.qualified(fact, route, catalog)
        latest = planner.select(data['facts'], route, now, catalog=catalog)['fact']
        report['latest_observation'] = describe(latest, now)
        result = planner.plan_facts(data, catalog)
        report['previous_current'] = describe(data.get('current'), now)
        decision = result['decision'];report['candidate_decision'] = decision
        approval = data.get('approval');approved = False
        if approval is not None:
            try:planner.check_approval(route, approval);approved = True
            except (ValueError, KeyError, TypeError):pass
        if not approved:
            report['required_approvals'].append('EXPLICIT_APPROVAL_OF_EXACT_ROUTE_SHA256')
            if route['enabled'] == '0':
                report['required_approvals'].append('EXPLICIT_DISABLED_ROUTE_PROJECTION_PERMISSION')
        if decision in ('INSERT', 'UPDATE'):
            report['candidate_projection'] = result['values']
            report['required_approvals'].append('SEPARATE_EXPLICIT_CURRENT_APPLY_ORDER')
        report['decision'] = 'BLOCKED' if decision in ('INSERT', 'UPDATE') and not approved else decision
        report['reason'] = 'ROUTE_APPROVAL_MISSING_OR_INVALID' if report['decision'] == 'BLOCKED' else REASONS[decision]
    except (ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report['reason'] = 'FACT_ROUTE_UNIT_TIME_OR_PROVENANCE_INVALID'
        if 'equal_time_conflict' in str(error):
            report['reason'] = 'OBSERVATION_TIME_CONFLICT'
        elif any(code in str(error) for code in ('current_origin_missing', 'current_projection_drift')):
            report['reason'] = 'CURRENT_PROVENANCE_INVALID'
        elif any(code in str(error) for code in ('timestamp', 'quote_clock')):
            report['reason'] = 'INVALID_MARKET_OR_OBSERVATION_TIME'
        report['candidate_projection'] = None
    return report


def snapshot_preview(snapshot):
    items = snapshot['items']
    planner.require(type(items) is list and len(items) == 5, 'preview_fixed_scope')
    scope = php(dict(operation='scope'), Path(__file__).with_name('preview_read.php'))['scope']
    planner.require({entry['isin'] for entry in items} == set(scope), 'preview_fixed_scope')
    seen = set();reports = []
    for entry in items:
        planner.require(entry['name'] == scope[entry['isin']], 'preview_scope_name')
        planner.require(entry['isin'] not in seen, 'preview_duplicate_scope');seen.add(entry['isin'])
        base = dict(isin=entry['isin'], name=entry['name'])
        if entry.get('blocked_reason'):
            reports.append(base | dict(decision='BLOCKED', reason='READ_SCOPE_OR_INPUT_REJECTED',
                required_approvals=['VERIFIED_READ_ONLY_SNAPSHOT'], business_writes=0));continue
        try:
            data = php(entry, Path(__file__).with_name('preview_read.php'))['input']
            planner.require(data['now'] == snapshot['as_of'], 'preview_snapshot_clock')
            reports.append(base | preview(data))
        except (ValueError, KeyError, TypeError, subprocess.SubprocessError):
            reports.append(base | dict(decision='BLOCKED', reason='QUALIFIED_REFERENCE_REJECTED',
                required_approvals=['VERIFIED_ASSET_SOURCE_ROUTE_UNIT_BINDING'], business_writes=0))
    return dict(as_of=snapshot['as_of'], reports=reports, business_writes=0, provider_requests=0)


def public_summary(report):
    # Explicit allowlist: no prices, IDs, dedupe hashes, timestamps, credentials or SQL.
    return dict(business_writes=0, provider_requests=0, reports=[
        {key: item[key] for key in ('name', 'decision', 'reason', 'required_approvals')} | dict(
            current_status=('CURRENT_VERIFIED' if item['previous_current'].get('verified') else 'CURRENT_UNVERIFIED')
                if item.get('previous_current') else ('CURRENT_MISSING' if 'previous_current' in item else 'CURRENT_UNKNOWN'),
            observation_status='VALID_OBSERVATION_PRESENT' if item.get('latest_observation') else 'NO_VERIFIED_OBSERVATION',
            candidate_decision=item.get('candidate_decision'))
        for item in report['reports']])


if __name__ == '__main__':
    try:print(json.dumps(dict(ok=True, preview=snapshot_preview(json.loads(sys.stdin.read())))))
    except (ValueError, KeyError, TypeError):print(json.dumps(dict(ok=False, failure='PREVIEW_INPUT_REJECTED')))
