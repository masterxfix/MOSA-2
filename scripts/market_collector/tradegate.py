"""ISIN-bound Tradegate quote adapter, ported from MOSA's working minute path.

Reference: masterxfix/fixlab 8b2d8c523aa4f63bef3aa904956b756ad87ab49f,
php/mosa_market_source_lab.php and php/mosa_market_live_quote_runner.php.
One orderbook page supplies the reported bid, ask and quote update time.
The stored price is their exact decimal midpoint, not a claimed last trade.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from html.parser import HTMLParser
import re
from zoneinfo import ZoneInfo

from .contracts import ObservationCandidate, require, validate_payload


MAX_RESPONSE_BYTES = 2_000_000


class _QuotePage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.text = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self._row = []
            self._cell = None
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = []
        elif tag == 'br' and self._cell is not None:
            self._cell.append(' ')

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._cell is not None and self._row is not None:
            self._row.append(' '.join(''.join(self._cell).split()))
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            self.rows.append(self._row)
            self._row = None
            self._cell = None

    def handle_data(self, data):
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def column(self, label):
        # MOSA uses the value in the row directly following the named header.
        for index, row in enumerate(self.rows[:-1]):
            if label in row:
                column = row.index(label)
                following = self.rows[index + 1]
                return following[column] if column < len(following) else None
        return None

    def row(self, label):
        for row in self.rows:
            if len(row) > 1 and row[0].casefold() == label.casefold():
                return row[1]
        return None


def _price(value):
    require(type(value) is str, 'Tradegate quote price missing')
    value = re.sub(r'[^0-9,.\-]', '', value)
    require(0 < len(value) <= 64, 'Tradegate quote price invalid')
    if ',' in value and '.' in value:
        value = (value.replace('.', '').replace(',', '.') if value.rfind(',') > value.rfind('.')
                 else value.replace(',', ''))
    elif ',' in value:
        value = value.replace(',', '.')
    require(re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', value) is not None,
            'Tradegate quote price invalid')
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError('Tradegate quote price invalid') from error
    require(result.is_finite() and result > 0, 'Tradegate positive quote required')
    return result


def _decimal(value):
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def _market_time(text, collected_at):
    match = re.search(r'Letzte Aktualisierung:\s*(\d{2}\.\d{2}\.\d{4})\s*@\s*(\d{2}:\d{2}:\d{2})', text)
    require(match is not None, 'Tradegate quote update time missing')
    try:
        local = datetime.strptime(match[1] + ' ' + match[2], '%d.%m.%Y %H:%M:%S')
        berlin = ZoneInfo('Europe/Berlin')
        first = local.replace(tzinfo=berlin, fold=0)
        second = local.replace(tzinfo=berlin, fold=1)
        require(first.utcoffset() == second.utcoffset(), 'Tradegate ambiguous local quote time')
        instant = first.astimezone(timezone.utc)
        require(instant.astimezone(berlin).replace(tzinfo=None) == local,
                'Tradegate nonexistent local quote time')
        captured = datetime.fromisoformat(collected_at).replace(tzinfo=timezone.utc)
        require(instant <= captured, 'Tradegate future quote time')
    except (ValueError, OverflowError) as error:
        raise ValueError('Tradegate invalid quote time: ' + str(error)) from error
    return instant.strftime('%Y-%m-%d %H:%M:%S.%f')


class TradegateQuoteV1:
    provider_key = 'tradegate_bsx_quote_v1'
    content_types = ('text/html', 'application/xhtml+xml')

    def live_request(self, instrument, instant, *, php_cli=None, request_script=None):
        """Reuse MOSA's one-page ISIN request; no lookup or implicit network call."""
        require(type(instrument) is str and re.fullmatch(r'[A-Z0-9]{12}', instrument),
                'qualified ISIN context required')
        return dict(
            url='https://www.tradegatebsx.com/orderbuch.php?isin=' + instrument,
            headers=['Accept: text/html,application/xhtml+xml',
                     'Referer: https://www.tradegatebsx.com/',
                     'User-Agent: FixLab-MOSA-Market-Source-Lab/2.0'],
            request_key='tradegate-quote:' + instrument, role='quote', series='snapshot')

    def normalize(self, payload, route):
        validate_payload(payload, content_types=self.content_types)
        require(payload.provider_key == route.provider_key == self.provider_key,
                'provider context mismatch')
        require(type(route.instrument) is str and re.fullmatch(r'[A-Z0-9]{12}', route.instrument),
                'qualified ISIN context required')
        require(0 < len(payload.payload_bytes) <= MAX_RESPONSE_BYTES,
                'Tradegate response size invalid')
        charset = re.search(r'charset\s*=\s*["\']?([^;\s"\']+)', payload.content_type, re.I)
        encoding = charset[1].lower() if charset else 'utf-8'
        require(encoding in ('utf-8', 'utf8', 'iso-8859-1', 'windows-1252'),
                'Tradegate unsupported character encoding')
        try:
            html = payload.payload_bytes.decode(encoding)
        except UnicodeDecodeError as error:
            raise ValueError('Tradegate invalid HTML encoding') from error
        page = _QuotePage()
        page.feed(html)
        page.close()
        text = ' '.join(' '.join(page.text).split())
        require((page.column('ISIN') or '').upper() == route.instrument, 'ISIN context mismatch')
        currency = (page.column('Handelswährung') or '').upper()
        if not re.fullmatch(r'[A-Z]{3}', currency):
            match = re.search(r'\bKurse in ([A-Z]{3})\b', text)
            currency = match[1] if match else ''
        require(currency == 'EUR', 'Tradegate EUR signal required')
        bid, ask = _price(page.row('Bid')), _price(page.row('Ask'))
        require(ask >= bid, 'Tradegate bid exceeds ask')
        with localcontext() as context:
            context.prec = 80
            mid = (bid + ask) / Decimal(2)
        market_at = _market_time(text, payload.collected_at)
        provenance = (
            ('provider_key', payload.provider_key), ('request_key', payload.request_key),
            ('payload_sha256', payload.payload_sha256), ('price_field_source', '(Bid+Ask)/2'),
            ('quote_type', 'mid'), ('bid_field_source', 'table.row[Bid]'),
            ('ask_field_source', 'table.row[Ask]'),
            ('time_field_source', 'Letzte Aktualisierung (Europe/Berlin)'),
            ('instrument_field_source', 'table.column[ISIN]'),
            ('unit_field_source', 'Handelswährung or Kurse in'),
            ('observed_at_source', 'CollectedPayload.collected_at'))
        return ObservationCandidate(route.route['asset_id'], payload.source_id, payload.route_id,
            market_at, payload.collected_at, _decimal(mid), _decimal(bid), _decimal(ask),
            None, 'EUR', payload.payload_sha256, provenance)
