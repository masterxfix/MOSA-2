"""Gettex MUND delayed post-trade file service, one bounded published UTC slot."""
from datetime import datetime, timedelta
import gzip
from io import BytesIO
import re

from .contracts import ObservationCandidate, require, validate_payload

FILE_BASE = 'https://erdk.bayerische-boerse.de:8000/delayed-data/MUNC-MUND/posttrade/'
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
STAMP = '%Y-%m-%d %H:%M:%S.%f'
FILE_STAMP = '%Y%m%d.%H.%M'


def file_slot(value):
    requested = datetime.strptime(value, STAMP)
    # Wait until the newest slot can have been published with its 15-minute delay.
    return requested.replace(minute=requested.minute // 15 * 15, second=0, microsecond=0) - timedelta(minutes=15)


class GettexDelayedTradeV1:
    provider_key = 'gettex_mund_delayed_v1'
    content_types = ('application/gzip', 'application/x-gzip', 'application/octet-stream')

    def live_request(self, instrument, instant, *, php_cli=None, request_script=None):
        require(type(instrument) is str and re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', instrument),
                'qualified ISIN context required')
        slot = file_slot(instant).strftime(FILE_STAMP)
        return dict(url=FILE_BASE+f'posttrade.{slot}.mund.csv.gz', headers=[],
                    request_key='gettex-mund:'+slot, max_bytes=MAX_FILE_BYTES)

    def normalize(self, payload, route):
        validate_payload(payload, content_types=self.content_types)
        require(payload.provider_key == route.provider_key == self.provider_key, 'provider context mismatch')
        require(re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', route.instrument), 'qualified ISIN context required')
        key = re.fullmatch(r'gettex-mund:(\d{8}\.\d{2}\.\d{2})', payload.request_key)
        require(key is not None, 'Gettex file identity mismatch')
        end = datetime.strptime(key[1], FILE_STAMP)
        newest = file_slot(payload.requested_at)
        require(end.minute % 15 == 0 and newest-timedelta(days=1) <= end <= newest, 'Gettex file timestamp')
        require(len(payload.payload_bytes) <= MAX_FILE_BYTES, 'Gettex compressed size')
        try:
            with gzip.GzipFile(fileobj=BytesIO(payload.payload_bytes)) as file:
                raw = file.read(MAX_UNCOMPRESSED_BYTES+1)
        except (EOFError, OSError) as error:
            raise ValueError('Gettex invalid gzip') from error
        require(len(raw) <= MAX_UNCOMPRESSED_BYTES, 'Gettex expanded size')
        start = end-timedelta(minutes=15)
        candidates = {}
        for line in raw.splitlines():
            parts = line.split(b',')
            if parts[0] != route.instrument.encode('ascii'):
                continue
            require(len(parts) == 5, 'Gettex posttrade columns')
            _, clock, currency, price, _ = (value.decode('ascii') for value in parts)
            require(re.fullmatch(r'\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?', clock), 'Gettex trade clock')
            time_format = '%H:%M:%S.%f' if '.' in clock else '%H:%M:%S'
            market = datetime.combine(start.date(), datetime.strptime(clock, time_format).time())
            if market < start and start.date() != end.date():
                market += timedelta(days=1)
            require(start <= market < end, 'Gettex trade outside file slot')
            require(re.fullmatch(r'[A-Z]{3}', currency), 'Gettex currency')
            require(re.fullmatch(r'[0-9]{1,18}(?:\.[0-9]{1,10})?', price) and any(c in '123456789' for c in price),
                    'Gettex trade price')
            require(candidates.setdefault(market, (currency, price)) == (currency, price), 'Gettex ambiguous market time')
        require(bool(candidates), 'Gettex trade unavailable')
        market = max(candidates)
        currency, price = candidates[market]
        provenance = (('provider_key', payload.provider_key), ('request_key', payload.request_key),
                      ('payload_sha256', payload.payload_sha256), ('price_field_source', 'posttrade.price'),
                      ('time_field_source', 'UTC file slot and posttrade.time'),
                      ('unit_field_source', 'posttrade.currency'),
                      ('observed_at_source', 'CollectedPayload.collected_at'),
                      ('venue', 'MUND'), ('quote_type', 'delayed_trade'))
        return ObservationCandidate(route.route['asset_id'], payload.source_id, payload.route_id,
            market.strftime(STAMP), payload.collected_at, price, None, None, None,
            currency, payload.payload_sha256, provenance)
