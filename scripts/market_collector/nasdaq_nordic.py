"""Official Nasdaq Nordic MiFID II post-trade publications, for private use."""
import csv
from datetime import datetime, timedelta, timezone
import io
import json
import re
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from .contracts import ObservationCandidate, require, validate_payload
from .gettex_delayed import STAMP
from .http_transport import HttpGet, ReadOnlyHttpTransport

BASE = "https://tradereports.nasdaq.com/api/regulatory/"
QUERY = {"type": "POST_TRADE", "assetClass": "EQUITY"}
FILE = re.compile(r"NordicEquity-posttrade-(\d{4}-\d{2}-\d{2}T\d{4})")
MAX_BYTES = 2 * 1024 * 1024
MARKETS = {"XSTO": ("SE", "SEK"), "XCSE": ("DK", "DKK"), "XHEL": ("FI", "EUR")}
COLUMNS = (
    "Trading date and time", "Instrument identification code", "Price", "Missing Price",
    "Price currency", "Price notation", "Quantity", "Venue of execution", "Trading system",
    "Publication date and time", "Venue of publication", "Transaction identification code", "Flags",
)


def publication_start(name):
    match = FILE.fullmatch(name)
    require(match is not None, "Nasdaq publication filename")
    local = datetime.strptime(match[1], "%Y-%m-%dT%H%M").replace(tzinfo=ZoneInfo("Europe/Stockholm"))
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def download_url(name):
    publication_start(name)
    return BASE + "trade-report/download?" + urlencode(QUERY | {"fileName": name})


def fetch(url, limit):
    return ReadOnlyHttpTransport(HttpGet(None, url, ()), timeout=8, max_bytes=limit).fetch(None)


def publications():
    response = fetch(BASE + "trade-reports?" + urlencode(QUERY), 256 * 1024)
    require(response.http_status == 200, "Nasdaq publication list unavailable")
    names = json.loads(response.payload_bytes)["reports"]
    require(isinstance(names, list), "Nasdaq publication list")
    return sorted({name for name in names if isinstance(name, str) and FILE.fullmatch(name)}, reverse=True)


def trades(raw, name):
    start = publication_start(name)
    end = start + timedelta(minutes=1)
    source = io.StringIO(raw.decode("utf-8-sig"), newline="")
    first = source.readline()
    if first.strip() != '"sep=;"':
        source.seek(0)
    rows = csv.DictReader(source, delimiter=";")
    require(tuple(rows.fieldnames or ()) == COLUMNS, "Nasdaq post-trade columns")
    for row in rows:
        mic = row["Venue of execution"]
        currency = row["Price currency"]
        price = row["Price"]
        isin = row["Instrument identification code"]
        flags = (row["Flags"] or "").split(",")
        if (mic not in MARKETS or MARKETS[mic][1] != currency or row["Price notation"] != "MONE"
                or row["Missing Price"] or "CANC" in flags or "AMND" in flags
                or not isinstance(isin, str) or re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin) is None
                or not isinstance(price, str) or re.fullmatch(r"[0-9]{1,18}(?:\.[0-9]{1,10})?", price) is None
                or not any(digit in "123456789" for digit in price)):
            continue
        published = exchange_time(row["Publication date and time"])
        market = exchange_time(row["Trading date and time"])
        if start <= published < end and market <= published:
            yield isin, mic, market, price, row["Transaction identification code"]


def exchange_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value):
        raise ValueError("Nasdaq UTC timestamp")
    return datetime.fromisoformat(value[:-1])


class NasdaqNordicTradeV1:
    provider_key = "nasdaq_nordic_delayed_v1"
    content_types = ("application/octet-stream", "text/csv")

    def archive_request(self, instrument, instant, name, mic):
        start = publication_start(name)
        captured = datetime.strptime(instant, STAMP)
        require(mic in MARKETS and start + timedelta(minutes=15) <= captured <= start + timedelta(days=2),
                "Nasdaq publication age")
        return dict(url=download_url(name), max_bytes=MAX_BYTES, request_key=mic + ":" + name)

    def normalize(self, payload, route):
        validate_payload(payload, content_types=self.content_types)
        require(payload.provider_key == route.provider_key == self.provider_key, "provider context mismatch")
        mic, name = payload.request_key.split(":", 1)
        self.archive_request(route.instrument, payload.requested_at, name, mic)
        candidates = [(market, trade_id, price) for isin, venue, market, price, trade_id
                      in trades(payload.payload_bytes, name) if isin == route.instrument and venue == mic]
        require(bool(candidates), "Nasdaq trade unavailable")
        market, _, price = max(candidates)
        provenance = (("provider_key", payload.provider_key), ("request_key", payload.request_key),
                      ("payload_sha256", payload.payload_sha256), ("price_field_source", "Price"),
                      ("time_field_source", "Trading date and time"), ("unit_field_source", "Price currency"),
                      ("observed_at_source", "CollectedPayload.collected_at"), ("venue", mic),
                      ("quote_type", "delayed_trade"))
        return ObservationCandidate(route.route["asset_id"], payload.source_id, payload.route_id,
            market.strftime(STAMP), payload.collected_at, price, None, None, None,
            MARKETS[mic][1], payload.payload_sha256, provenance)
