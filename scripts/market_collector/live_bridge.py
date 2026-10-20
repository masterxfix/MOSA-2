"""Credential-free bridge: acquire once before the transaction, bind only actual IDs in it."""
import base64
from dataclasses import asdict
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.market_collector.contracts import Request, RouteContract
from scripts.market_collector.collector import FixtureTransport
from scripts.market_collector.http_transport import HttpGet, ReadOnlyHttpTransport
from scripts.market_collector.normalizer import pipeline, writer
from scripts.phase3o.live_plan import transport, restore


def run(data):
    action = data['action']
    if action == 'runtime':
        writer.observation.catalog_module.normative_catalog()
        return dict(ok=True, database_connections=0, provider_requests=0)
    if action == 'fetch':
        private = Path(data['private_root'])
        manifest = json.loads((private/'live-manifest.json').read_text())
        module = manifest['adapter_module']
        if not module.startswith('scripts.market_collector.') or not module.rsplit('.', 1)[1].replace('_', '').isalnum():
            raise ValueError('adapter module')
        adapter = getattr(importlib.import_module(module), manifest['adapter_class'])()
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')
        endpoint = adapter.live_request(manifest['instrument'], stamp,
            php_cli=data['php_cli'], request_script=str(private/'request.php'))
        http = ReadOnlyHttpTransport(HttpGet(None, endpoint['url'],
            tuple(tuple(h.split(': ', 1)) for h in endpoint['headers'])), timeout=25)
        fd = os.open(private/'provider-consumed.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        response = http.fetch(None)
        if response.http_status != 200:
            raise ValueError('provider response')
        return dict(ok=True, provider_requests=1, response=transport(asdict(response)),
            request_key=endpoint['request_key'], requested_at=stamp,
            provider_key=adapter.provider_key, adapter_module=module,
            adapter_class=manifest['adapter_class'], instrument=manifest['instrument'])
    if action == 'plan':
        acquired = data['acquired']
        from scripts.market_collector.contracts import TransportResponse
        adapter = getattr(importlib.import_module(acquired['adapter_module']), acquired['adapter_class'])()
        binding = data['route']
        request = Request(acquired['provider_key'], binding['source_id'], binding['id'],
            acquired['request_key'], acquired['requested_at'], acquired['instrument'])
        response = TransportResponse(**restore(acquired['response']))
        route = RouteContract(request.provider_key, request.instrument, 2, binding)
        result = pipeline(request, route, FixtureTransport({request: response}), [adapter],
            catalog=writer.observation.catalog_module.normative_catalog(),
            created_at=data['created_at'], existing=restore(data['existing']))
        allowed = ('INSERT', 'DUPLICATE_UNCHANGED') if data.get('allow_duplicate') is True else ('INSERT',)
        if result['decision'] not in allowed:
            raise ValueError('writer decision')
        return dict(ok=True, plan=transport(result['writer_plan']))
    if action == 'replay':
        planner = writer.WriterPlanner(writer.observation.catalog_module.normative_catalog(),
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
