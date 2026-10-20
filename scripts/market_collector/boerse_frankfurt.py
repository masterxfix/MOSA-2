"""Börse Frankfurt price_information snapshot; no transport or identity search."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import re
import subprocess

from .contracts import ObservationCandidate, require, validate_payload


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'ambiguous JSON member')
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError('non-finite JSON number')


def market_time(value):
    # Strict offset-bearing ISO subset; never truncate fractional microseconds.
    require(type(value) is str and re.fullmatch(
        r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
        r'(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])', value),
        'offset-bearing ISO market time required')
    try:
        utc = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
        require(1000 <= utc.year <= 9999, 'market time outside DATETIME range')
        return utc.strftime('%Y-%m-%d %H:%M:%S.%f')
    except (ValueError, OverflowError) as error:
        raise ValueError('invalid ISO market time') from error


class FrankfurtSnapshotV1:
    provider_key = 'boerse_frankfurt_api_v1'

    def live_request(self, instrument, instant, *, php_cli, request_script):
        """Reuse the qualified historical request descriptor; no DB or identity discovery."""
        require(type(instrument) is str and re.fullmatch(r'[A-Z0-9]{12}', instrument), 'qualified ISIN context required')
        reply = subprocess.run([php_cli, request_script], input=json.dumps(
            dict(isin=instrument, instant=instant+' UTC')).encode(), capture_output=True, timeout=10)
        require(reply.returncode == 0 and not reply.stderr, 'provider request descriptor')
        endpoint = json.loads(reply.stdout)
        expected = 'https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin='+instrument+'&mic=XFRA'
        require(endpoint['url'] == expected and endpoint['role'] == 'price_information'
                and endpoint['series'] == 'snapshot', 'qualified snapshot request')
        return endpoint

    def normalize(self, payload, route):
        validate_payload(payload)
        require(payload.provider_key == route.provider_key == self.provider_key, 'provider context mismatch')
        require(type(route.instrument) is str and re.fullmatch(r'[A-Z0-9]{12}', route.instrument), 'qualified ISIN context required')
        document = json.loads(payload.payload_bytes.decode('utf-8'), parse_float=Decimal,
                              parse_constant=invalid_constant, object_pairs_hook=unique_object)
        require(type(document) is dict, 'snapshot object required')
        require(document.get('isin') == route.instrument, 'ISIN context mismatch')
        require(document.get('mic') == 'XFRA', 'MIC context mismatch')
        currency = document.get('currency')
        require(type(currency) is dict and currency.get('originalValue') == 'EUR', 'Frankfurt EUR signal required')
        price = document.get('lastPrice')
        require(type(price) in (int, Decimal), 'native numeric lastPrice required')
        # Fixed-point conversion is bounded; precision/range rejection stays in
        # the existing writer. Large/small exponent strings reach it unchanged.
        native = str(price)
        if type(price) is Decimal and price.is_finite() and -10 <= price.as_tuple().exponent <= 18 and price.adjusted() < 18:
            native = format(price, 'f')
        provenance = (('provider_key', payload.provider_key), ('request_key', payload.request_key),
            ('payload_sha256', payload.payload_sha256), ('price_field_source', '$.lastPrice'),
            ('time_field_source', '$.timestampLastPrice'), ('instrument_field_source', '$.isin'),
            ('mic_field_source', '$.mic'), ('unit_field_source', '$.currency.originalValue'),
            ('observed_at_source', 'CollectedPayload.collected_at'))
        return ObservationCandidate(route.route['asset_id'], payload.source_id, payload.route_id,
            market_time(document.get('timestampLastPrice')), payload.collected_at,
            native, None, None, None, 'EUR', payload.payload_sha256, provenance)
