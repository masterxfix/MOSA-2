"""Yahoo Chart v1: one native snapshot; provider knowledge stays in this adapter."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import re
import subprocess
from urllib.parse import urlsplit, parse_qs, quote

from .contracts import ObservationCandidate, require, validate_payload

META = '$.chart.result[0].meta.'


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'ambiguous JSON member')
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError('non-finite JSON number')


class YahooChartSnapshotV1:
    provider_key = 'yahoo_finance_chart_v1'

    def live_request(self, instrument, instant, *, php_cli, request_script):
        """Consume an existing qualified private descriptor; never discover symbols."""
        require(type(instrument) is str and re.fullmatch(r'[A-Za-z0-9^][A-Za-z0-9.^=_-]{0,63}', instrument),
                'qualified symbol context required')
        reply = subprocess.run([php_cli, request_script], input=json.dumps(
            dict(symbol=instrument, instant=instant+' UTC')).encode(), capture_output=True, timeout=10)
        require(reply.returncode == 0 and not reply.stderr, 'provider request descriptor')
        endpoint = json.loads(reply.stdout)
        url = urlsplit(endpoint['url'])
        require(url.scheme == 'https' and url.netloc == 'query1.finance.yahoo.com'
                and url.path == '/v8/finance/chart/'+quote(instrument, safe='')
                and not url.fragment and parse_qs(url.query, strict_parsing=True) ==
                    {'interval':['1d'], 'range':['1d']}
                and endpoint['series'] == 'snapshot' and endpoint['role'] == 'chart_snapshot',
                'qualified snapshot request')
        require(type(endpoint['headers']) is list and type(endpoint['request_key']) is str,
                'provider request descriptor')
        return endpoint

    def normalize(self, payload, route):
        validate_payload(payload)
        require(payload.provider_key == route.provider_key == self.provider_key, 'provider context mismatch')
        document = json.loads(payload.payload_bytes.decode('utf-8'), parse_float=Decimal,
                              parse_constant=invalid_constant, object_pairs_hook=unique_object)
        require(type(document) is dict and type(document.get('chart')) is dict, 'chart required')
        chart = document['chart']
        require(chart.get('error') is None, 'provider chart error')
        results = chart.get('result')
        require(type(results) is list and len(results) == 1 and type(results[0]) is dict, 'single chart result required')
        meta = results[0].get('meta')
        require(type(meta) is dict, 'snapshot meta required')
        require(type(meta.get('symbol')) is str and meta['symbol'] == route.instrument, 'symbol context mismatch')
        # Provider spellings are understood here only. No monetary projection.
        units = {'GBp': 'GBX', 'GBX': 'GBX', 'EUR': 'EUR', 'GBP': 'GBP'}
        require(type(meta.get('currency')) is str and meta['currency'] in units, 'unsupported provider unit')
        price = meta.get('regularMarketPrice')
        require(type(price) in (int, Decimal), 'native numeric snapshot price required')
        if type(price) is Decimal:
            require(price.is_finite() and -10 <= price.as_tuple().exponent <= 18 and price.adjusted() < 18,
                    'native price precision exceeds writer contract')
        native = format(price, 'f') if type(price) is Decimal else str(price)
        epoch = meta.get('regularMarketTime')
        require(type(epoch) is int, 'integer Unix-seconds market time required')
        try:
            market = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=epoch)
            require(1000 <= market.year <= 9999, 'market time outside DATETIME range')
        except OverflowError as error:
            raise ValueError('market time outside DATETIME range') from error
        provenance = (('provider_key', payload.provider_key), ('request_key', payload.request_key),
            ('payload_sha256', payload.payload_sha256), ('price_field_source', META+'regularMarketPrice'),
            ('time_field_source', META+'regularMarketTime'), ('symbol_field_source', META+'symbol'),
            ('unit_field_source', META+'currency'), ('observed_at_source', 'CollectedPayload.collected_at'))
        return ObservationCandidate(route.route['asset_id'], payload.source_id, payload.route_id,
            market.strftime('%Y-%m-%d %H:%M:%S.%f'), payload.collected_at, native, None, None, None,
            units[meta['currency']], payload.payload_sha256, provenance)
