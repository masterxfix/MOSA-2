"""Single-use, anonymous HTTPS GET transport. No provider request construction."""
from dataclasses import dataclass
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request

from .contracts import Request, TransportResponse, require


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')


@dataclass(frozen=True)
class HttpGet:
    request: Request | None  # None permits acquisition before transaction-owned route allocation.
    url: str
    headers: tuple[tuple[str, str], ...] = ()

    def __post_init__(self):
        require(self.request is None or type(self.request) is Request, 'bound collector request required')
        require(type(self.url) is str, 'HTTPS URL required')
        parsed = urllib.parse.urlsplit(self.url)
        require(parsed.scheme == 'https' and bool(parsed.hostname) and parsed.port in (None, 443)
                and parsed.username is None and parsed.password is None and not parsed.fragment, 'anonymous HTTPS URL required')
        require(type(self.headers) is tuple, 'immutable headers required')
        names = set()
        for pair in self.headers:
            require(type(pair) is tuple and len(pair) == 2 and all(type(v) is str for v in pair), 'header pair required')
            name, value = pair
            require(name and all(c.isascii() and (c.isalnum() or c == '-') for c in name), 'header name required')
            require('\r' not in value and '\n' not in value, 'invalid header value')
            lower = name.lower()
            require(lower not in {'authorization', 'proxy-authorization', 'cookie', 'cookie2', 'host'}, 'credentials/cookies/host override forbidden')
            require(lower not in names, 'duplicate header');names.add(lower)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ReadOnlyHttpTransport:
    def __init__(self, endpoint, *, timeout=20):
        require(type(endpoint) is HttpGet, 'qualified GET descriptor required')
        require(type(timeout) in (int, float) and 0 < timeout <= 60, 'bounded timeout required')
        self.endpoint = endpoint
        self.timeout = timeout
        self.attempt_count = 0
        self.request_started_at = None
        self.response_ended_at = None
        self.last_response = None
        self.last_error = None

    def fetch(self, request):
        require(request == self.endpoint.request, 'HTTP request binding mismatch')
        require(self.attempt_count == 0, 'single-use transport already consumed')
        self.attempt_count = 1  # Consume even on failure; no retry or second fetch.
        self.request_started_at = utc_now()
        req = urllib.request.Request(self.endpoint.url, headers=dict(self.endpoint.headers), method='GET')
        # Ignore ambient authenticated proxies. No auth handler or cookie jar.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        try:
            try:
                response = opener.open(req, timeout=self.timeout)
            except urllib.error.HTTPError as error:
                response = error  # Preserve original error/redirect body, no follow-up.
            with response:
                body = response.read()
                status = response.code
                content_type = response.headers.get('Content-Type', '')
            self.response_ended_at = utc_now()
            self.last_error = None if 200 <= status < 300 else 'http_error'
            self.last_response = TransportResponse(body, self.response_ended_at, status, content_type,
                'OK' if self.last_error is None else 'ERROR', self.last_error)
            return self.last_response
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            self.response_ended_at = utc_now()
            self.last_error = ('timeout' if isinstance(error, TimeoutError)
                or isinstance(getattr(error, 'reason', None), TimeoutError) else 'network_error')
            raise ValueError('read_only_http_'+self.last_error) from None
