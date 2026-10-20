"""Immediate market shell, accessible markup and disclosure guards."""
from html.parser import HTMLParser
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('home_deploy', ROOT / 'scripts/deploy_sftp.py')
DEPLOY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEPLOY)


class Markup(HTMLParser):
    """Strict structural checks for this deliberately small HTML vocabulary."""
    VOID = {'meta', 'link', 'br'}
    ALLOWED = VOID | set('html head title script body a header span main section div h1 h2 h3 p strong time article dl dt dd ol li aside ul footer table caption thead tbody tr th td noscript'.split())

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
        cls.js = (ROOT / 'assets/js/page_load_time.js').read_text(encoding='utf-8')
        visible = DEPLOY.VisibleHTML()
        visible.feed(cls.html)
        cls.text = ' '.join(' '.join(visible.text).split())

    def test_visible_purpose_and_verified_results(self):
        for text in ['MOSA 2', 'Marktdaten', 'Gespeicherte Kurse', 'Marktzeit', 'Erfassungszeit',
                     'Letzter gespeicherter Stand','Asset','Kurs','Quelle / Handelsplatz','Datenstatus']:
            with self.subTest(text=text):
                self.assertIn(text, self.text)

    def test_import_result_and_remaining_limits_are_unambiguous(self):
        for text in ['Keine automatische Aktualisierung.', 'ausschließlich gespeicherte Daten',
                     'Fehlende Angaben bleiben offen', 'keine Echtzeitzusage', 'Keine Produktivfreigabe',
                     'Marktdaten werden geladen', 'Mit Daten']:
            with self.subTest(text=text):
                self.assertIn(text, self.text)
        for obsolete in ['Echtzeitkurse verfügbar']:
            self.assertNotIn(obsolete, self.text)

    def test_original_overview_is_preserved_and_market_follows_results(self):
        original = re.sub(r'    <section class="market-section".*?</section>\n\n', '', self.html, flags=re.S)
        original = original.replace('  <script src="assets/js/market.js" defer></script>\n', '')
        original = original.replace('assets/css/main.css?v=homecopy-20261020', 'assets/css/main.css?v=footer-20261019')
        original = original.replace('<br>Mit Daten · <span data-data-ready-time aria-label="Datenladezeit wird gemessen">— ms</span>', '')
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), '94d2c7509133ffbe2082ac647753371f19d3f9abe904d98fd4bc22be8e816bdd')
        for removed in ['Finanzen, Depot und Markt verstehen', 'Die Daten liefern die Fakten.', 'Die KI hilft beim Verstehen.', 'class="principles"']:
            self.assertNotIn(removed, self.html)
        self.assertRegex(self.html, r'<h1 id="projekt-titel">MOSA 2</h1>')
        order = [self.html.index(value) for value in ['class="results"', 'class="market-section"', 'class="next-step"', 'class="progress-section"']]
        self.assertEqual(order, sorted(order))

    def test_public_files_contain_no_internal_or_credential_details(self):
        source = self.html + self.css + self.js
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
        self.assertIn('data-market-rows',self.html)
        self.assertEqual(parser.tags.count('table'),1)
        self.assertEqual(parser.tags.count('th'),5)
        self.assertIn('aria-busy="true"',self.html)

    def test_deferred_local_scripts_and_no_external_dependencies(self):
        self.assertNotRegex(self.html.lower(), r'<(?:iframe|form|input)\b|\son\w+=')
        scripts = re.findall(r'<script\b([^>]*)>(.*?)</script\s*>', self.html, re.S | re.I)
        self.assertEqual(len(scripts), 2)
        self.assertEqual(scripts[0], (' src="assets/js/page_load_time.js" defer', ''))
        self.assertEqual(scripts[1], (' src="assets/js/market.js" defer', ''))
        self.assertNotRegex(self.html + self.css, r'https?://|@import|url\(')
        self.assertEqual(re.findall(r'<link[^>]+href="([^"]+)"', self.html),
                         ['assets/css/main.css?v=homecopy-20261020'])
        self.assertIn('@media (max-width: 600px)', self.css)
        self.assertIn('@media (max-width: 900px)', self.css)
        self.assertNotIn('animation:', self.css)
        self.assertIn(':focus-visible', self.css)

    def test_footer_fallback_and_responsive_contract(self):
        footer = self.html.split('<footer', 1)[1].split('</footer>', 1)[0]
        self.assertIn('Seitenladezeit · ', footer)
        self.assertIn('data-page-load-time', footer)
        self.assertIn('>— ms</span>', footer)
        self.assertIn('aria-label="Seitenladezeit wird gemessen"', footer)
        self.assertIn('MOSA 2 · Auf verlässlichen Grundlagen aufgebaut.', footer)
        self.assertIn('Entwicklung · Keine Produktivfreigabe', footer)
        self.assertIn('grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr)', self.css)
        self.assertIn('font-variant-numeric: tabular-nums', self.css)
        mobile = self.css.split('@media (max-width: 600px)', 1)[1]
        self.assertIn('.footer { grid-template-columns: 1fr;', mobile)

    def test_timing_runtime_is_local_and_only_reads_navigation_performance(self):
        self.assertIn('performance.getEntriesByType("navigation")', self.js)
        self.assertIn('window.addEventListener("load"', self.js)
        self.assertIn('window.setTimeout(show, 0)', self.js)
        self.assertNotRegex(self.js, r'fetch|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|document\.cookie|https?://')
        for obsolete in ['Current 0,096 ms', 'History 0,167 ms', 'Bars 0,196 ms']:
            self.assertNotIn(obsolete, self.html)

    def test_existing_deployment_validator_accepts_homepage(self):
        DEPLOY.validate_html(self.html.encode('utf-8'))


@unittest.skipUnless(shutil.which('node'), 'Existing Node.js required for browser-runtime fixture')
class PageLoadRuntimeTests(unittest.TestCase):
    """Execute the real local script in an isolated, offline browser fixture."""
    def run_duration(self, duration, *, mode='normal'):
        harness = r'''
const vm = require('node:vm');
const fs = require('node:fs');
const options = JSON.parse(process.argv[2]);
const node = {textContent: '— ms', attributes: {}, setAttribute(k,v) {this.attributes[k]=v;}};
let load, task, calls = [], listeners = [];
let duration = options.duration;
if (options.mode === 'nan') duration = NaN;
if (options.mode === 'infinity') duration = Infinity;
const performance = {};
if (options.mode !== 'no-api') performance.getEntriesByType = type => {
  calls.push(type);
  return options.mode === 'no-entry' ? [] : [{duration}];
};
const context = {
  document: {querySelector: selector => options.mode === 'no-node' ? null : node},
  performance,
  window: {addEventListener(type, fn, config) {listeners.push([type,config]); load=fn;},
           setTimeout(fn, delay) {if(delay!==0) throw Error('Unexpected delay'); task=fn;}}
};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const before = {text:node.textContent,calls:calls.length};
if(load) load();
const duringLoad = {text:node.textContent,calls:calls.length};
if(task) task();
process.stdout.write(JSON.stringify({before,duringLoad,text:node.textContent,
  aria:node.attributes['aria-label'],title:node.title,calls,listeners}));
'''
        result = subprocess.run([shutil.which('node'), '-e', harness,
                                 str(ROOT / 'assets/js/page_load_time.js'),
                                 json.dumps({'duration': duration, 'mode': mode})],
                                capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_updates_only_after_load_event_finishes(self):
        result = self.run_duration(126.4)
        self.assertEqual(result['before'], {'text':'— ms','calls':0})
        self.assertEqual(result['duringLoad'], result['before'])
        self.assertEqual(result['listeners'], [['load', {'once':True}]])
        self.assertEqual(result['calls'], ['navigation'])
        self.assertEqual(result['text'], '126 ms')
        self.assertEqual(result['aria'], 'Seitenladezeit 126 ms')
        self.assertEqual(result['title'], 'Seitenladezeit: 126 ms')

    def test_milliseconds_seconds_german_format_and_rounded_threshold(self):
        for value, expected in [(0,'0 ms'), (83.6,'84 ms'), (927,'927 ms'),
                                (999.4,'999 ms'), (999.5,'1,00 s'), (1000,'1,00 s'),
                                (1030,'1,03 s'), (1240,'1,24 s'), (2480,'2,48 s')]:
            with self.subTest(value=value):
                self.assertEqual(self.run_duration(value)['text'], expected)

    def test_invalid_or_unavailable_values_keep_fallback(self):
        for value, mode in [(-1,'normal'), (None,'normal'), ('126','normal'),
                             (None,'nan'), (None,'infinity'), (None,'no-entry'),
                             (None,'no-api'), (None,'no-node')]:
            with self.subTest(value=value,mode=mode):
                result = self.run_duration(value,mode=mode)
                self.assertEqual(result['text'], '— ms')
                self.assertNotIn('aria', result)


if __name__ == '__main__':
    unittest.main()
