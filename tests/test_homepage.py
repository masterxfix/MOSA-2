"""Public, static project overview: content, markup and disclosure guards."""
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('home_deploy', ROOT / 'scripts/deploy_sftp.py')
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class Markup(HTMLParser):
    """Strict structural checks for this deliberately small HTML vocabulary."""
    VOID = {'meta', 'link', 'br'}
    ALLOWED = VOID | set('html head title body a header span main section div h1 h2 h3 p strong time article dl dt dd ol li aside ul footer'.split())

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.ids, self.links, self.tags = [], [], [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag not in self.ALLOWED:
            self.errors.append('Unexpected element: ' + tag)
        if len(dict(attrs)) != len(attrs):
            self.errors.append('Duplicate attribute')
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'href' in attrs:
            self.links.append(attrs['href'])
        if tag == 'li' and (not self.stack or self.stack[-1] not in {'ol', 'ul'}):
            self.errors.append('Invalid list child')
        if tag in {'section', 'article', 'div', 'h1', 'h2', 'h3', 'p'} and 'p' in self.stack:
            self.errors.append('Block inside paragraph')
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append('Unbalanced element: ' + tag)
        else:
            self.stack.pop()


class HomepageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'index.html').read_text(encoding='utf-8')
        cls.css = (ROOT / 'assets/css/main.css').read_text(encoding='utf-8')
        visible = DEPLOY.VisibleHTML()
        visible.feed(cls.html)
        cls.text = ' '.join(' '.join(visible.text).split())

    def test_visible_purpose_and_verified_results(self):
        for text in ['MOSA 2', 'Persönliche, finanzorientierte', 'Daten- und KI-Plattform.',
                     'deterministisch', 'Die KI hilft beim Verstehen.', 'Core-Schema',
                     'Technisch freigegeben', '13 Tabellen', 'Version 1', '11 / 11 geprüft']:
            with self.subTest(text=text):
                self.assertIn(text, self.text)

    def test_no_real_data_and_next_goal_are_unambiguous(self):
        for text in ['Noch keine echten MOSA-Daten.', 'zwölf Fachtabellen sind leer',
                     'Schema-Ledger) enthält einen Eintrag', 'keine Live-Daten',
                     'Marktdaten – Current + History', 'Geplant', 'Current', 'History',
                     'Noch nicht begonnen', 'Depotdaten', 'News', 'KI-Auswertung auf MOSA-2-Daten',
                     'Keine Produktivfreigabe', '18. Oktober 2026']:
            with self.subTest(text=text):
                self.assertIn(text, self.text)

    def test_public_files_contain_no_internal_or_credential_details(self):
        source = self.html + self.css
        for pattern in [r'h29077', r'configcenter', r'scharwerk', r'localhost', r'127\.0\.0\.1',
                        r'\b(?:\d{1,3}\.){3}\d{1,3}\b', r'\b(?:3307|8443)\b',
                        r'\b[a-f0-9]{40,64}\b', r'[A-Z]:[\\/]', r'/var/',
                        r'password|secret|token|credential|passwort|zugangsdaten',
                        r'plesk|dogado|KI-Kontrollzentrum|m2_entities', r'pdo|mysql:']:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, source, re.I))

    def test_structural_html_and_accessible_landmarks(self):
        parser = Markup()
        parser.feed(self.html)
        parser.close()
        self.assertEqual(parser.errors, [])
        self.assertEqual(parser.stack, [])
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for tag in ['html', 'head', 'body', 'title', 'main', 'h1']:
            self.assertEqual(parser.tags.count(tag), 1)
        for link in parser.links:
            if link.startswith('#'):
                self.assertIn(link[1:], parser.ids)
        self.assertTrue(self.html.lower().startswith('<!doctype html>'))
        self.assertIn('<html lang="de">', self.html)
        self.assertIn('name="viewport"', self.html)
        self.assertEqual(self.html.count('data-status='), 6)

    def test_no_runtime_or_external_dependencies(self):
        self.assertNotRegex(self.html.lower(), r'<(?:script|iframe|form|input)\b|\son\w+=')
        self.assertNotRegex(self.html + self.css, r'https?://|@import|url\(')
        self.assertEqual(re.findall(r'<link[^>]+href="([^"]+)"', self.html), ['assets/css/main.css'])
        self.assertIn('@media (max-width: 600px)', self.css)
        self.assertIn('@media (max-width: 900px)', self.css)
        self.assertNotIn('animation:', self.css)
        self.assertIn(':focus-visible', self.css)

    def test_existing_deployment_validator_accepts_homepage(self):
        DEPLOY.validate_html(self.html.encode('utf-8'))


if __name__ == '__main__':
    unittest.main()
