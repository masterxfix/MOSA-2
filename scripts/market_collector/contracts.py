"""Immutable transport and native-candidate contracts; no persistence API."""
from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType
from typing import Protocol

from scripts.phase3n.writer_plan import observation

require = observation.require
PAYLOAD_CONTRACT = 'mosa2-collected-payload-v1'


def key(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', value), 'invalid request/provider key')
    return value


def identity(value):
    require(type(value) is str and observation.shared('identity', value=value) == value, 'canonical qualified identity required')
    return value


def timestamp(value):
    return observation.shared('timestamp', value=value)


@dataclass(frozen=True)
class Request:
    provider_key: str
    source_id: str
    route_id: str
    request_key: str
    requested_at: str  # Caller-supplied UTC, never an implicit wall clock.
    instrument: str   # Generic qualified request context, not an endpoint URL.


@dataclass(frozen=True)
class TransportResponse:
    payload_bytes: bytes
    collected_at: str
    http_status: int
    content_type: str
    transport_status: str = 'OK'
    transport_error: str | None = None

    def __post_init__(self):
        require(type(self.payload_bytes) is bytes, 'immutable response bytes required')


@dataclass(frozen=True)
class CollectedPayload:
    contract_version: str
    provider_key: str
    source_id: str
    route_id: str
    request_key: str
    requested_at: str
    collected_at: str
    http_status: int
    content_type: str
    payload_sha256: str
    payload_bytes: bytes
    transport_status: str = 'OK'
    transport_error: str | None = None

    def __post_init__(self):
        require(type(self.payload_bytes) is bytes, 'immutable payload bytes required')


@dataclass(frozen=True)
class RouteContract:
    """Qualified caller sidecar plus the unchanged Phase-3N route envelope."""
    provider_key: str
    instrument: str
    format_version: int
    route: object

    def __post_init__(self):
        # Route values are exactly the Phase-3N scalar fields; no nested state.
        require(type(self.route) is dict, 'route snapshot required')
        require(all(type(v) in (str, int, type(None)) for v in self.route.values()), 'scalar route fields required')
        object.__setattr__(self, 'route', MappingProxyType(dict(self.route)))

    def envelope(self):
        return dict(format_version=self.format_version, route=dict(self.route))


@dataclass(frozen=True)
class ObservationCandidate:
    asset_id: str
    source_id: str
    route_id: str
    market_at: str
    observed_at: str
    native_price: str
    native_bid: str | None
    native_ask: str | None
    native_volume: str | None
    provider_unit: str
    payload_sha256: str
    provenance: tuple[tuple[str, str], ...]

    def __post_init__(self):
        require(type(self.provenance) is tuple and all(type(pair) is tuple and len(pair) == 2
                and all(type(v) is str for v in pair) for pair in self.provenance), 'immutable provenance pairs required')


class Transport(Protocol):
    def fetch(self, request: Request) -> TransportResponse: ...


class ProviderAdapter(Protocol):
    provider_key: str

    def normalize(self, payload: CollectedPayload, route: RouteContract) -> ObservationCandidate: ...


def validate_payload(payload):
    require(type(payload) is CollectedPayload, 'collected payload required')
    require(payload.contract_version == PAYLOAD_CONTRACT, 'unsupported payload contract')
    require(type(payload.payload_bytes) is bytes, 'original immutable bytes required')
    require(hashlib.sha256(payload.payload_bytes).hexdigest() == payload.payload_sha256, 'payload hash mismatch')
    require(payload.transport_status == 'OK' and payload.transport_error is None, 'transport failed')
    require(type(payload.http_status) is int and 200 <= payload.http_status < 300, 'HTTP response unsuccessful')
    require(type(payload.content_type) is str and payload.content_type.split(';')[0].strip().lower() == 'application/json', 'JSON content type required')
