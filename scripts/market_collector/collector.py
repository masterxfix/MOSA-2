"""Provider-neutral byte collection. The only supplied transport is offline."""
import hashlib
from types import MappingProxyType

from .contracts import (CollectedPayload, PAYLOAD_CONTRACT, Request, TransportResponse,
                        identity, key, require, timestamp)


class FixtureTransport:
    """Exact frozen Request -> Response binding, without URLs or live fallback."""
    def __init__(self, responses):
        require(all(type(k) is Request and type(v) is TransportResponse for k, v in responses.items()), 'fixture bindings')
        self._responses = MappingProxyType(dict(responses))

    def fetch(self, request):
        require(request in self._responses, 'fixture request not found')
        return self._responses[request]


class Collector:
    def __init__(self, adapters):
        registry = {}
        for adapter in adapters:
            provider = key(adapter.provider_key)
            require(provider not in registry, 'duplicate provider adapter')
            registry[provider] = adapter
        self._adapters = MappingProxyType(registry)

    def adapter(self, provider_key):
        require(provider_key in self._adapters, 'unsupported provider adapter')
        return self._adapters[provider_key]

    def collect(self, request, transport):
        require(type(request) is Request, 'request description required')
        key(request.provider_key);key(request.request_key)
        identity(request.source_id);identity(request.route_id)
        require(type(request.instrument) is str and bool(request.instrument.strip()), 'qualified request instrument required')
        requested = timestamp(request.requested_at)
        self.adapter(request.provider_key)  # Select before accepting response bytes.
        response = transport.fetch(request)
        require(type(response) is TransportResponse and type(response.payload_bytes) is bytes, 'transport response bytes required')
        require(type(response.http_status) is int and 100 <= response.http_status <= 599, 'HTTP status required')
        require(type(response.content_type) is str and bool(response.content_type.strip()), 'content type required')
        require(response.transport_status in ('OK', 'ERROR'), 'transport status required')
        require(response.transport_error is None or key(response.transport_error), 'transport error code')
        require((response.transport_status == 'OK') == (response.transport_error is None), 'transport status/error mismatch')
        collected = timestamp(response.collected_at)
        require(collected >= requested, 'collection precedes request')
        return CollectedPayload(PAYLOAD_CONTRACT, request.provider_key, request.source_id, request.route_id,
            request.request_key, requested, collected, response.http_status, response.content_type,
            hashlib.sha256(response.payload_bytes).hexdigest(), response.payload_bytes,
            response.transport_status, response.transport_error)
