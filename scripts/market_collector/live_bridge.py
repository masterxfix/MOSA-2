"""Credential-free bridge: acquire once before the transaction, bind only actual IDs in it."""
import base64
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
import stat
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.market_collector.contracts import Request, RouteContract, TransportResponse
from scripts.market_collector.collector import FixtureTransport
from scripts.market_collector.http_transport import HttpGet, ReadOnlyHttpTransport
from scripts.market_collector.normalizer import pipeline, writer
from scripts.phase3o.live_plan import transport, restore


def run(data):
    action = data['action']
    if action == 'runtime':
        writer.observation.catalog_module.runtime_catalog()
        return dict(ok=True, database_connections=0, provider_requests=0)
    if action == 'fetch':
        private = Path(data['private_root'])
        manifest = json.loads((private/'live-manifest.json').read_text())
        module = manifest['adapter_module']
        if not module.startswith('scripts.market_collector.') or not module.rsplit('.', 1)[1].replace('_', '').isalnum():
            raise ValueError('adapter module')
        adapter = getattr(importlib.import_module(module), manifest['adapter_class'])()
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')
        archive = manifest.get('gettex_archive')
        if archive is None:
            endpoint = adapter.live_request(manifest['instrument'], stamp,
                php_cli=data['php_cli'], request_script=data.get('request_script', str(private/'request.php')))
        else:
            if adapter.provider_key != 'gettex_mund_delayed_v1':
                raise ValueError('archive provider binding')
            stamp = archive.get('captured_at', stamp)
            endpoint = adapter.archive_request(manifest['instrument'], stamp, archive['slot'])
        if archive is not None and 'private_path' in archive:
            source = Path(archive['private_path'])
            parent = private.resolve().parents[2]
            if source.parent != parent or source.name != 'mosa2-gettex-posttrade.'+archive['slot']+'.mund.csv.gz':
                raise ValueError('private archive binding')
            with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                    raise ValueError('private archive metadata')
                raw = stream.read(endpoint['max_bytes']+1)
            if len(raw) > endpoint['max_bytes']:
                raise ValueError('private archive size')
            response = TransportResponse(raw, stamp, 200, 'application/gzip')
            requests, provider_duration_ms = 0, 0
        else:
            http = ReadOnlyHttpTransport(HttpGet(None, endpoint['url'],
                tuple(tuple(h.split(': ', 1)) for h in endpoint['headers'])), timeout=25,
                max_bytes=endpoint.get('max_bytes', 2 * 1024 * 1024))
            fd = os.open(private/'provider-consumed.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
            started = time.monotonic()
            response = http.fetch(None)
            requests, provider_duration_ms = 1, (time.monotonic() - started) * 1000
            if response.http_status != 200:
                raise ValueError('provider response')
        if archive is not None and hashlib.sha256(response.payload_bytes).hexdigest() != archive['sha256']:
            raise ValueError('archive content changed')
        return dict(ok=True, provider_requests=requests, provider_duration_ms=provider_duration_ms, response=transport(asdict(response)),
            request_key=endpoint['request_key'], requested_at=stamp,
            provider_key=adapter.provider_key, adapter_module=module,
            adapter_class=manifest['adapter_class'], instrument=manifest['instrument'])
    if action == 'qualify':
        # A clearly labelled nonpersistent sidecar, never a claimed physical DB route.
        acquired, binding = data['acquired'], data['route']
        result = run(dict(action='plan', acquired=acquired, route=binding,
                          created_at=acquired['requested_at'], existing=[]))
        normalized = result['plan']['normalized']
        return dict(ok=True, scope='NON_PERSISTENT_TEST_ROUTE',
                    currency=normalized['currency'], quote_unit_key=normalized['quote_unit_key'],
                    quote_unit_version=normalized['quote_unit_version'],
                    market_at=normalized['market_at'], observed_at=normalized['observed_at'])
    if action == 'plan':
        acquired = data['acquired']
        binding = data['route']
        catalog = writer.observation.catalog_module.runtime_catalog()
        existing = restore(data['existing'])
        if 'm2_market_observation' in acquired:
            fact = acquired['m2_market_observation']
            raw = {key: fact[key] for key in
                   ('currency', 'market_at', 'observed_at', 'price', 'bid', 'ask', 'volume')}
            raw.update(asset_id=binding['asset_id'], source_id=binding['source_id'], route_id=binding['id'])
            raw.update({key: binding[key] for key in writer.UNIT_FIELDS})
            route = RouteContract(fact['provider'], acquired['instrument'], 2, binding)
            planner = writer.WriterPlanner(catalog, [route.envelope()], existing)
            plan = planner.plan(raw, format_version=2, intent='NEW_NATIVE_V2', created_at=data['created_at'])
            result = dict(decision=plan['decision'], writer_plan=plan)
        else:
            adapter = getattr(importlib.import_module(acquired['adapter_module']), acquired['adapter_class'])()
            request = Request(acquired['provider_key'], binding['source_id'], binding['id'],
                acquired['request_key'], acquired['requested_at'], acquired['instrument'])
            response = TransportResponse(**restore(acquired['response']))
            route = RouteContract(request.provider_key, request.instrument, 2, binding)
            result = pipeline(request, route, FixtureTransport({request: response}), [adapter],
                catalog=catalog, created_at=data['created_at'], existing=existing)
        if result['decision'] == 'INSERT' and data.get('allow_duplicate') is True:
            candidate = result['writer_plan']['normalized']
            matches = [fact['payload'] for fact in existing if fact['format_version'] == 2 and
                       all(fact['payload'][key] == candidate[key] for key in
                           ('asset_id', 'source_id', 'route_id', 'market_at'))]
            if matches:
                prior = min(matches, key=lambda fact: fact['observed_at'])
                normalized = writer.observation.normalize_observation(prior, catalog)
                if any(normalized[key] != value for key, value in candidate.items() if key != 'observed_at'):
                    raise ValueError('conflicting market snapshot')
                planner = writer.WriterPlanner(catalog, [route.envelope()], existing)
                old_plan = planner.plan(prior, format_version=2, intent='NEW_NATIVE_V2',
                                        created_at=data['created_at'])
                if old_plan['decision'] != 'DUPLICATE_UNCHANGED':
                    raise ValueError('unchanged snapshot replay')
                result = dict(decision=old_plan['decision'], writer_plan=old_plan)
        allowed = ('INSERT', 'DUPLICATE_UNCHANGED') if data.get('allow_duplicate') is True else ('INSERT',)
        if result['decision'] not in allowed:
            raise ValueError('writer decision')
        return dict(ok=True, plan=transport(result['writer_plan']))
    if action == 'replay':
        planner = writer.WriterPlanner(writer.observation.catalog_module.runtime_catalog(),
            [dict(format_version=2, route=data['route'])], restore(data['existing']))
        plan = planner.plan(data['stored'], format_version=2, intent='NEW_NATIVE_V2', created_at=data['created_at'])
        if plan['decision'] != 'DUPLICATE_UNCHANGED':
            raise ValueError('replay decision')
        return dict(ok=True, plan=transport(plan))
    raise ValueError('action')


if __name__ == '__main__':
    try:
        print(json.dumps(run(json.loads(sys.stdin.read()))))
    except Exception as error:
        print(json.dumps(dict(ok=False, failure=type(error).__name__)))
