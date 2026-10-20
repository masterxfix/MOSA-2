"""Offline fakes only: exercise the new request boundary, never the provider."""
from io import BytesIO
from pathlib import Path
import socket
import sqlite3
import unittest
from unittest.mock import Mock, patch
import urllib.error

from scripts.market_collector.contracts import Request
from scripts.market_collector.http_transport import HttpGet, NoRedirect, ReadOnlyHttpTransport


class Response(BytesIO):
    code = 200
    headers = {'Content-Type':'application/json; charset=utf-8','Set-Cookie':'must-not-be-retained=1'}


class ReadOnlyTransportTests(unittest.TestCase):
    def setUp(self):
        self.request=Request('synthetic_v1','201','301','synthetic-get','2001-01-01 10:00:00.000000','SYNTHETIC')
        self.endpoint=HttpGet(self.request,'https://example.invalid/snapshot?instrument=SYNTHETIC',(('Accept','application/json'),))

    def test_get_exact_bytes_metadata_and_actual_request_bound(self):
        opener=Mock();opener.open.return_value=Response(b' {"price": 42}\n')
        transport=ReadOnlyHttpTransport(self.endpoint)
        with patch('urllib.request.build_opener',return_value=opener), \
             patch('scripts.market_collector.http_transport.utc_now',side_effect=['2001-01-01 10:00:01.000000','2001-01-01 10:00:02.123456']):
            response=transport.fetch(self.request)
        req=opener.open.call_args.args[0]
        self.assertEqual(req.get_method(),'GET');self.assertIsNone(req.data)
        self.assertFalse(req.has_header('Cookie'));self.assertFalse(req.has_header('Authorization'))
        self.assertEqual(response.payload_bytes,b' {"price": 42}\n')
        self.assertEqual(response.http_status,200);self.assertEqual(response.content_type,Response.headers['Content-Type'])
        self.assertEqual(response.collected_at,'2001-01-01 10:00:02.123456')
        self.assertEqual(transport.request_started_at,'2001-01-01 10:00:01.000000')
        self.assertEqual(transport.response_ended_at,response.collected_at)
        self.assertFalse(hasattr(transport,'cookies'))

    def test_no_redirect_proxy_auth_or_cookie_handler(self):
        opener=Mock();opener.open.return_value=Response(b'{}')
        with patch('urllib.request.build_opener',return_value=opener) as build:
            ReadOnlyHttpTransport(self.endpoint).fetch(self.request)
        proxy,redirect=build.call_args.args
        self.assertEqual(proxy.proxies,{})
        self.assertIsInstance(redirect,NoRedirect)
        self.assertIsNone(redirect.redirect_request(None,None,302,'redirect',{},'https://another.invalid'))

    def test_anonymous_https_and_safe_headers_only(self):
        for url in ('http://example.invalid','https://user:password@example.invalid','https://example.invalid:444/path'):
            with self.subTest(url=url),self.assertRaises(ValueError):HttpGet(self.request,url)
        for name,value in (('Cookie','x'),('Authorization','x'),('Host','another.invalid'),('Accept','x\r\nInjected: true')):
            with self.subTest(name=name),self.assertRaises(ValueError):
                HttpGet(self.request,self.endpoint.url,((name,value),))

    def test_http_error_body_and_status_preserved_once(self):
        opener=Mock();opener.open.side_effect=urllib.error.HTTPError(self.endpoint.url,403,'Forbidden',
            {'Content-Type':'application/json'},BytesIO(b'{"error":"denied"}'))
        transport=ReadOnlyHttpTransport(self.endpoint)
        with patch('urllib.request.build_opener',return_value=opener):response=transport.fetch(self.request)
        self.assertEqual(response.http_status,403);self.assertEqual(response.payload_bytes,b'{"error":"denied"}')
        self.assertEqual(response.transport_status,'ERROR');self.assertEqual(response.transport_error,'http_error')
        self.assertEqual(opener.open.call_count,1)

    def test_network_failure_has_no_secret_diagnostics_or_retry(self):
        opener=Mock();opener.open.side_effect=urllib.error.URLError('secret detail must not escape')
        transport=ReadOnlyHttpTransport(self.endpoint)
        with patch('urllib.request.build_opener',return_value=opener):
            with self.assertRaisesRegex(ValueError,'^read_only_http_network_error$'):transport.fetch(self.request)
            with self.assertRaisesRegex(ValueError,'single-use'):transport.fetch(self.request)
        self.assertEqual(opener.open.call_count,1);self.assertEqual(transport.attempt_count,1)
        self.assertIsNotNone(transport.response_ended_at)

    def test_timeout_and_mismatched_request_fail_closed(self):
        opener=Mock();opener.open.side_effect=TimeoutError('private details')
        transport=ReadOnlyHttpTransport(self.endpoint)
        with patch('urllib.request.build_opener',return_value=opener):
            with self.assertRaisesRegex(ValueError,'^read_only_http_timeout$'):transport.fetch(self.request)
        self.assertEqual(opener.open.call_count,1)
        with self.assertRaisesRegex(ValueError,'binding'):ReadOnlyHttpTransport(self.endpoint).fetch(None)

    def test_single_use_after_success_no_database_or_real_socket(self):
        opener=Mock();opener.open.return_value=Response(b'{}')
        transport=ReadOnlyHttpTransport(self.endpoint)
        with patch.object(socket,'socket',side_effect=AssertionError('offline test')), \
             patch.object(sqlite3,'connect',side_effect=AssertionError('no database')), \
             patch('urllib.request.build_opener',return_value=opener):
            transport.fetch(self.request)
            with self.assertRaisesRegex(ValueError,'single-use'):transport.fetch(self.request)
        self.assertEqual(opener.open.call_count,1)
        source=(Path(__file__).resolve().parents[1]/'scripts/market_collector/http_transport.py').read_text()
        for forbidden in ('frankfurt','yahoo','lastPrice','WriterPlanner','sqlite','mysql','CookieJar'):
            self.assertNotIn(forbidden,source)


if __name__=='__main__':unittest.main()
