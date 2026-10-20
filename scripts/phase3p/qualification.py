"""Pure route-revision proposals and the existing writer's offline history plan.

No database, provider, filesystem writer, route allocation or Current selection.
Callers must independently qualify identity, source, historical payload and times.
"""
import copy
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('phase3p_actual_writer',Path(__file__).resolve().parents[1]/'phase3n/writer_plan.py')
writer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)
require=writer.require
UNIT_FIELDS=writer.UNIT_FIELDS
UINT32=4294967295


def revision_number(value):
    return int(writer.observation.units.integer(value,UINT32))


def unique_keys(route):
    for field in ('asset_id','source_id'):
        require(writer.observation.shared('identity',value=route[field])==route[field],'canonical unique-key identity')
    return ((route['source_id'],route['route_type'],route['external_key'],revision_number(route['route_revision'])),
            (route['asset_id'],route['source_id'],route['route_type'],revision_number(route['route_revision'])))


def check_unique(proposal,routes):
    external,group=unique_keys(proposal)
    for route in routes:
        a,b=unique_keys(route)
        require(a!=external,'source/external/revision conflict')
        require(b!=group,'asset/source/revision conflict')


def revision_proposal(legacy,routes,binding,catalog):
    """Describe a new physical revision, without assigning its future database ID."""
    legacy=copy.deepcopy(legacy);routes=copy.deepcopy(routes)
    require(sum(route==legacy for route in routes)==1,'qualified legacy snapshot required')
    require(all(legacy[field] is None for field in UNIT_FIELDS),'legacy unit fields must remain NULL')
    for field in ('id','asset_id','source_id'):
        require(writer.observation.shared('identity',value=legacy[field])==legacy[field],'canonical route identity')
    for field in ('route_type','external_key'):
        require(type(legacy[field]) is str and bool(legacy[field]),'qualified role and provider key required')
    require(set(binding)==set(UNIT_FIELDS),'complete unit binding')
    semantic,_=writer.observation.binding(binding,catalog)
    revisions=[]
    for route in routes:
        unique_keys(route)  # Reject type aliases before grouping or comparing keys.
        # A revision is never a way to move a provider instrument to another asset.
        same_source=route['source_id']==legacy['source_id'] and route['route_type']==legacy['route_type']
        same_external=same_source and route['external_key']==legacy['external_key']
        same_group=same_source and route['asset_id']==legacy['asset_id']
        require(not same_external or route['asset_id']==legacy['asset_id'],'provider instrument identity conflict')
        require(not same_group or route['external_key']==legacy['external_key'],'route group instrument conflict')
        if same_external or same_group:revisions.append(revision_number(route['route_revision']))
    next_revision=max(revisions)+1
    require(next_revision<=UINT32,'route revision exhausted')
    proposal={field:legacy[field] for field in ('asset_id','source_id','route_type','external_key')}
    proposal.update(route_revision=str(next_revision),**semantic)
    check_unique(proposal,routes)
    return proposal


def history_plan(raw,route_envelopes,existing,created_at,catalog):
    """Return the actual Phase-3N plan; no persistence or second canonicalization."""
    planner=writer.WriterPlanner(catalog,route_envelopes,existing)
    return planner.plan(copy.deepcopy(raw),format_version=2,intent='NEW_NATIVE_V2',
                        representation='native',created_at=created_at)
