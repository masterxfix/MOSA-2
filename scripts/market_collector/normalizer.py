"""Provider-neutral candidate -> existing Observation-v2 WriterPlanner pipeline."""
from scripts.phase3n import writer_plan as writer

from .collector import Collector
from .contracts import identity, require, timestamp, validate_payload


def raw_observation(candidate, payload, route, catalog):
    validate_payload(payload)
    require(type(route.format_version) is int and route.format_version == 2, 'unit-aware v2 route required')
    require(set(route.route) == {'id', 'asset_id', 'source_id', 'route_revision'} | set(writer.UNIT_FIELDS), 'route fields')
    row = dict(route.route)
    for field in ('id', 'asset_id', 'source_id'):identity(row[field])
    writer.observation.units.integer(row['route_revision'], 4294967295)
    semantic, quote = writer.observation.binding(row, catalog)
    require(candidate.asset_id == row['asset_id'] and candidate.source_id == payload.source_id == row['source_id']
            and candidate.route_id == payload.route_id == row['id'], 'candidate/route identity mismatch')
    require(candidate.provider_unit == quote['unit_key'], 'provider unit/route mismatch')
    require(candidate.payload_sha256 == payload.payload_sha256, 'candidate payload hash mismatch')
    provenance = dict(candidate.provenance)
    require(len(provenance) == len(candidate.provenance), 'duplicate provenance field')
    for field in ('provider_key', 'request_key', 'payload_sha256'):
        require(provenance.get(field) == getattr(payload, field), 'provenance binding mismatch')
    for field in ('price_field_source', 'time_field_source'):
        require(type(provenance.get(field)) is str and bool(provenance[field]), 'field provenance required')
    require(candidate.observed_at == payload.collected_at, 'observed time must be collector time')
    require(candidate.native_volume is None, 'snapshot history volume is unqualified')
    require(all(semantic[f] is None for f in writer.UNIT_FIELDS[3:]), 'snapshot quantity/volume binding is unqualified')
    return dict(asset_id=candidate.asset_id, source_id=candidate.source_id, route_id=candidate.route_id,
        currency=quote['monetary_currency_code'], market_at=timestamp(candidate.market_at),
        observed_at=timestamp(candidate.observed_at), price=candidate.native_price, bid=candidate.native_bid,
        ask=candidate.native_ask, volume=None, **semantic)


def pipeline(request, route, transport, adapters, *, catalog, created_at, existing=()):
    """Return an offline plan only. Caller supplies every ID, route and timestamp."""
    result = dict(decision='REJECT', collector_status='NOT_RUN', payload_sha256=None,
        adapter_status='NOT_RUN', normalizer_status='NOT_RUN', collected_payload=None,
        candidate=None, writer_decision='NOT_RUN', dedupe_key=None, canonical_bytes=None, route_binding=None)
    stage = 'collector'
    try:
        require(request.provider_key == route.provider_key and request.instrument == route.instrument,
                'request/route provider instrument mismatch')
        require(request.source_id == route.route['source_id'] and request.route_id == route.route['id'], 'request/route identity mismatch')
        collector = Collector(adapters)
        payload = collector.collect(request, transport)
        result.update(collector_status='COLLECTED', payload_sha256=payload.payload_sha256, collected_payload=payload)
        stage = 'adapter'
        candidate = collector.adapter(request.provider_key).normalize(payload, route)
        result.update(adapter_status='NORMALIZED', candidate=candidate)
        stage = 'normalizer'
        raw = raw_observation(candidate, payload, route, catalog)
        result['normalizer_status'] = 'NORMALIZED'
        stage = 'writer'
        planner = writer.WriterPlanner(catalog, [route.envelope()], existing)
        plan = planner.plan(raw, format_version=2, intent='NEW_NATIVE_V2', representation='native', created_at=created_at)
        result.update(decision=plan['decision'], writer_decision=plan['decision'], writer_plan=plan,
            dedupe_key=plan.get('dedupe_key'), canonical_bytes=plan.get('canonical_bytes'), route_binding=plan.get('route_binding'))
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        result[stage+'_status' if stage != 'writer' else 'writer_decision'] = 'REJECT'
        result.update(reason=str(error), rejected_stage=stage)
    return result
