"""Pure evidence gates; authority comes from the caller's bound private records.

No evidence discovery or persistence. Planning delegates to the Phase-3N writer
through Phase 3P only after every prerequisite has independently been qualified.
"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('phase3q_prior', Path(__file__).resolve().parents[1]/'phase3p/qualification.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)

IDENTITY_FIELDS = ('source_identifier_type', 'source_identifier_value', 'historical_name',
                   'historical_asset_class', 'historical_provider_instrument', 'historical_source_type')


def identity_status(records):
    """Combine referenced attestations without filling missing values or aliases."""
    if not records or any(type(r) is not dict or not r.get('evidence_reference') for r in records):
        return 'OPEN'
    complete = True
    for field in IDENTITY_FIELDS:
        values = [r.get(field) for r in records if r.get(field) is not None]
        if any(type(v) is not str or not v.strip() for v in values):
            return 'OPEN'
        if len(set(values)) > 1:
            return 'CONFLICT'
        complete = complete and bool(values)
    return 'PASS' if complete else 'OPEN'


def qualify(records, *, target, source_id, route, provenance, reimport):
    """Return one classification and explicit blockers, never allocate identities.

    PRESENT means an actual target group; ABSENT means a new group is needed.
    A missing target cannot acquire a synthetic route revision through this gate.
    Provenance loss must be positively attested before requesting gap acceptance.
    """
    prior.require(reimport in ('OPEN', 'MATCH', 'NO_MATCH'), 'reimport status')
    prior.require(route.get('status') in ('OPEN', 'PRESENT', 'ABSENT'), 'route group status')
    identity = identity_status(records)
    blockers = []
    new_masterdata = target.get('identifier_matches') == 0
    result = dict(classification='AUTHORITATIVE_SOURCE_REQUIRED', identity=identity,
                  new_masterdata_required=new_masterdata, reimport=reimport,
                  route_group=route['status'], actual_revision='OPEN', dry_run='NOT_RUN', blockers=blockers)
    if identity == 'CONFLICT' or type(target.get('identifier_matches')) is int and target['identifier_matches'] > 1:
        result.update(classification='IDENTITY_CONFLICT');blockers.append('identity_conflict');return result
    if identity != 'PASS':blockers.append('identity_incomplete')
    if type(target.get('identifier_matches')) is not int or target['identifier_matches'] != 1 or target.get('asset_id') is None:
        blockers.append('target_asset_unresolved')
    if source_id is None:blockers.append('source_unresolved')
    if route['status'] != 'PRESENT' or route.get('qualified') is not True:
        blockers.append('target_route_unqualified')
    if not blockers:
        for value in (target['asset_id'], source_id, route.get('id')):
            prior.require(prior.writer.observation.shared('identity', value=value) == value, 'canonical qualified identity')
        result['actual_revision'] = str(prior.revision_number(route.get('revision')))
    if provenance.get('raw_payload') is not True or provenance.get('deployment_binding') is not True:
        blockers.append('provenance_incomplete')
        if (blockers == ['provenance_incomplete'] and reimport == 'NO_MATCH'
                and provenance.get('permanently_unavailable') is True
                and provenance.get('remaining_contract_complete') is True):
            result['classification'] = 'PROVENANCE_GAP_ACCEPTANCE_REQUIRED'
    if reimport != 'NO_MATCH':blockers.append('v1_match' if reimport == 'MATCH' else 'v1_comparison_open')
    if not blockers:result['classification'] = 'IMPORT_READY'
    return result


def history_plan(records, *, target, source_id, route, provenance, reimport,
                 raw, route_envelopes, existing, created_at, catalog):
    result = qualify(records, target=target, source_id=source_id, route=route,
                     provenance=provenance, reimport=reimport)
    if result['classification'] != 'IMPORT_READY':return result, None
    prior.require(raw['asset_id'] == target['asset_id'] and raw['source_id'] == source_id
                  and raw['route_id'] == route['id'], 'plan identity must match qualified evidence')
    matches = [e['route'] for e in route_envelopes if e['route']['id'] == route['id']]
    prior.require(len(matches) == 1 and matches[0]['route_revision'] == result['actual_revision'], 'qualified route revision')
    plan = prior.history_plan(raw, route_envelopes, existing, created_at, catalog)
    result['dry_run'] = plan['decision']
    if plan['decision'] != 'INSERT':
        result['classification'] = 'IDENTITY_CONFLICT' if plan['decision'] == 'CONFLICT' else 'AUTHORITATIVE_SOURCE_REQUIRED'
        result['blockers'].append('writer_'+plan['decision'].lower())
    return result, plan
