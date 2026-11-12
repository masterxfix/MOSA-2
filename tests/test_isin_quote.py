"""ISIN-only UI and provider preview tests. No network, DB or hosting actions."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IsinQuoteTests(unittest.TestCase):
    def test_bounded_preview_parsers_and_exact_midpoint(self):
        php = shutil.which("php")
        self.assertIsNotNone(php)
        syntax = subprocess.run([php, "-l", str(ROOT / "api/isin_quote.php")],
                                capture_output=True, text=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr + syntax.stdout)
        result = subprocess.run([php, str(ROOT / "tests/fixtures/isin_quote_test.php")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("PASS synthetic ISIN quote tests", result.stdout)

    def test_all_four_mosa_providers_in_real_shared_source_core(self):
        php = shutil.which("php")
        self.assertIsNotNone(php)
        for file in ("api/isin_quote.php", "api/market_source_engine.php",
                     "tests/fixtures/isin_quote_all_test.php"):
            result = subprocess.run([php, "-l", str(ROOT / file)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        result = subprocess.run([php, str(ROOT / "tests/fixtures/isin_quote_all_test.php")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("PASS all four MOSA providers", result.stdout)

    def test_existing_design_preserved_and_fixed_five_replaced(self):
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        market = (ROOT / "marktdaten.html").read_text(encoding="utf-8")
        style = (ROOT / "assets/css/main.css").read_text(encoding="utf-8")
        js = (ROOT / "assets/js/isin_quotes.js").read_text(encoding="utf-8")
        self.assertNotRegex(home, r'data-isin-(list|form|input|count|clear|table)')
        self.assertNotIn('data-isin-stored-quotes', home)
        self.assertNotIn('Unser Entwicklungsweg', home)
        self.assertIn('NOVA fachlich nutzen', home)
        self.assertNotIn('aria-label="Fünf Aktien in der Marktdatenansicht"', home)
        self.assertNotIn('>PNE AG</a>', home)
        self.assertIn('data-isin-count', market)
        self.assertEqual(market.count('data-isin-form'), 1)
        self.assertIn('data-isin-input', market)
        self.assertNotIn('data-isin-steps', market)
        self.assertIn('data-isin-table data-isin-actions', market)
        self.assertIn('data-isin-clear', market)
        self.assertIn('<th scope="col">Wertpapier</th><th scope="col">Typ</th>', market)
        self.assertIn('assets/js/isin_quotes.js?v=market-registry-live-7', market)
        self.assertNotIn('assets/js/observations.js', market)
        self.assertIn('--bg: #10151c;', style)
        self.assertIn('--accent: #a5c9d9;', style)
        self.assertIn('font-family: Inter, "Segoe UI", system-ui, sans-serif;', style)
        self.assertIn('localStorage.getItem(KEY)', js)
        self.assertIn('fetch("api/isin_quote.php"', js)
        self.assertIn('form.addEventListener("submit"', js)

    def test_get_never_triggers_collection_and_mosa_provider_hosts_are_fixed(self):
        code = (ROOT / "api/isin_quote.php").read_text(encoding="utf-8")
        self.assertIn("REQUEST_METHOD", code)
        self.assertIn("'POST'", code)
        self.assertIn("SOURCE_UNSUPPORTED", code)
        self.assertIn("https://www.tradegatebsx.com/orderbuch.php?isin=", code)
        self.assertIn("https://api.live.deutsche-boerse.com/v1/data/price_information/single?isin=", code)
        self.assertIn("api/market_source_engine.php".replace("api/", ""), code)
        original = (ROOT / "api/market_source_engine.php").read_text(encoding="utf-8")
        self.assertIn("fixlabRunMosaMarketSourceLab", original)
        self.assertIn("lang_schwarz_quote", original)
        self.assertIn("tradegate_trade", original)
        self.assertIn("yahoo_home_market", original)
        self.assertIn("boerse_frankfurt_trade", original)
        self.assertIn("query1.finance.yahoo.com", original)
        self.assertIn("www.ls-tc.de", original)
        for forbidden in ("INSERT INTO ", "UPDATE m2_", "DELETE FROM ", "exec('DROP", "workflow_dispatch"):
            self.assertNotIn(forbidden, code)

    def test_browser_js_syntax_when_node_available(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js not installed")
        result = subprocess.run([node, "--check", str(ROOT / "assets/js/isin_quotes.js")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        scenario = subprocess.run([node, str(ROOT / "tests/isin_browser_check.cjs")],
                                  capture_output=True, text=True)
        self.assertEqual(scenario.returncode, 0, scenario.stderr + scenario.stdout)
        self.assertIn("PASS client click", scenario.stdout)


if __name__ == "__main__":
    unittest.main()
