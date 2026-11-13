"""Regression checks for the M2 Home page and its shared navigation."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("index.html", "marktdaten.html", "home.html")


class HomePageTests(unittest.TestCase):
    def test_generated_entry_pages_are_current(self):
        result = subprocess.run(
            [sys.executable, "scripts/build_pages.py", "--check"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_navigation_contains_exactly_one_home_link_on_all_pages(self):
        for name in (*PAGES, "anbieter-labor.html"):
            with self.subTest(name=name):
                page = (ROOT / name).read_text(encoding="utf-8")
                links = re.findall(r'<a\b[^>]*href="home.html"[^>]*>Home</a>', page)
                self.assertEqual(len(links), 1, name)
                self.assertIn('data-page="home"', links[0])
                self.assertEqual('aria-current="page"' in links[0], name == "home.html")
                self.assertIn('href="marktdaten.html"', page)
                self.assertIn('href="anbieter-labor.html"', page)

    def test_home_has_shared_shell_and_accessible_sections(self):
        page = (ROOT / "home.html").read_text(encoding="utf-8")
        fragment = (ROOT / "assets/main-home.html").read_text(encoding="utf-8").strip()
        self.assertIn(fragment, page)
        self.assertIn('<title>MOSA 2 · Home</title>', page)
        self.assertIn('<body class="home-page" data-site-shell>', page)
        self.assertIn('id="inhalt"', page)
        self.assertIn('data-codex-status', page)
        self.assertIn('data-nova-status', page)
        self.assertIn('data-reader-status', page)
        for section in ('m2-home-devices', 'm2-home-automation', 'm2-home-network'):
            self.assertIn('id="' + section + '"', page)
        self.assertIn('data-page-load-time', page)
        self.assertIn('data-home-device-state', page)

    def test_no_fictitious_controls_or_private_network_data(self):
        home = (ROOT / "assets/main-home.html").read_text(encoding="utf-8")
        self.assertIn("Nicht verbunden", home)
        self.assertIn("keine Schaltbefehle", home)
        self.assertNotIn("<button", home)
        self.assertNotIn("<form", home)
        self.assertNotIn("onclick=", home)
        self.assertNotRegex(home, r"192\.168\.|172\.1[6-9]\.|10\.\d+\.|api[_-]?key|password|token")

    def test_shared_market_view_and_navigation_remain_usable(self):
        market = (ROOT / "marktdaten.html").read_text(encoding="utf-8")
        navigation = (ROOT / "assets/js/navigation.js").read_text(encoding="utf-8")
        self.assertIn("data-isin-table", market)
        self.assertIn("data-isin-form", market)
        self.assertIn('next.dataset.page', navigation)
        self.assertIn("assets/main-", navigation)
        self.assertIn('href="home.html"', (ROOT / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
