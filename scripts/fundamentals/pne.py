"""Official German PNE annual-results release adapter. No network or database."""
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
import re

URL = 'https://www.pnegroup.com/newsroom/einzelansicht/pne-ag-schliesst-geschaeftsjahr-2025-operativ-erfolgreich-ab/'
ISIN = 'DE000A0JBPG2'
SOURCE = dict(source_key='pne_official_news', source_type='issuer_release', display_name='PNE AG official releases', base_url='https://www.pnegroup.com/', enabled='0')
METRICS = {
    'total_output': ('Gesamtleistung', 'Reported consolidated total output; not revenue.'),
    'ebitda': ('EBITDA', 'Reported consolidated earnings before interest taxes depreciation and amortisation; includes special effects.'),
    'ebitda_normalised': ('Normalisiertes EBITDA', 'Consolidated EBITDA excluding issuer-defined one-off non-operating special effects; not unadjusted EBITDA.'),
    'ebit': ('EBIT', 'Reported consolidated operating earnings before interest and taxes.'),
}
MONTHS = dict(Januar=1, Februar=2, März=3, April=4, Mai=5, Juni=6, Juli=7, August=8, September=9, Oktober=10, November=11, Dezember=12)
NUMBER = r'-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?'

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if not self.hidden:
            self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden:
            self.parts.append(' ')
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)

def normalized_text(raw):
    parser = Text()
    parser.feed(raw.decode('utf-8', errors='strict'))
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()

def number(value):
    if not re.fullmatch(NUMBER, value):
        raise ValueError('NUMBER')
    return format(Decimal(value.replace('.', '').replace(',', '.')), 'f')

def parse(raw, observed_at):
    text = normalized_text(raw)
    headings = list(re.finditer(r'Cuxhaven, (\d{1,2})\. ('+'|'.join(MONTHS)+r') (\d{4})\s*[–—-]\s*Die PNE AG hat das Geschäftsjahr (\d{4}) operativ erfolgreich abgeschlossen', text))
    if len(headings) != 1:
        raise ValueError('ANNUAL_RELEASE_IDENTITY')
    head = headings[0]
    published = date(int(head[3]), MONTHS[head[2]], int(head[1])).isoformat()
    year = int(head[4])
    if year != 2025 or not str(year + 1) == head[3] or published > observed_at[:10]:
        raise ValueError('REPORT_PERIOD')
    tail = re.search(r'Den Bericht für das Geschäftsjahr '+str(year)+r' hat PNE heute veröffentlicht\.', text[head.end():])
    if tail is None:
        raise ValueError('RESULTS_SECTION')
    section_end = head.end() + tail.end()
    section = text[head.start():section_end]
    # Bound actual results before outlook/Guidance sections; require exactly one match per metric.
    patterns = {
        'total_output': r'Die Gesamtleistung stieg auf ('+NUMBER+r') Mio\. Euro \(Vorjahr:\s*('+NUMBER+r') Mio\. Euro\)',
        'ebitda_normalised': r'Das um Sondereffekte bereinigte EBITDA\s*\([^)]*normalised EBITDA[^)]*\) erreichte ('+NUMBER+r') Mio\.(?: Euro)?(?= und)',
        'ebitda': r'Mit ('+NUMBER+r') Mio\. Euro \(Vorjahr:\s*('+NUMBER+r') Mio\. Euro\) liegt das EBITDA',
        'ebit': r'Im Geschäftsjahr '+str(year)+r' erzielte das Unternehmen ein Betriebsergebnis \(EBIT\) von ('+NUMBER+r') Mio\. Euro \(Vorjahr:\s*('+NUMBER+r') Mio\. Euro\)',
    }
    candidates = []
    for key, pattern in patterns.items():
        matches = list(re.finditer(pattern, section))
        if len(matches) != 1:
            raise ValueError('AMBIGUOUS_OR_MISSING_' + key.upper())
        match = matches[0]
        for index, value in enumerate(match.groups()):
            fiscal_year = year - index
            start, end = head.start() + match.start(index + 1), head.start() + match.end(index + 1)
            candidates.append(dict(metric_key=key, value_decimal=number(value), unit_key='EUR_MILLION', unit_version='1',
                period_type='fy', fiscal_year=str(fiscal_year), fiscal_quarter=None,
                period_start=f'{fiscal_year}-01-01', period_end=f'{fiscal_year}-12-31', estimate_horizon=None,
                as_of_at=None, reported_at=None, observed_at=observed_at,
                field_path=f'html-text-v1:{start}:{end};publication-date={published};date-only;PNE-calendar-FY',
                value_type='decimal', dimension_key='monetary', value_text=None, value_date=None))
    return dict(publication_date=published, parser_key='pne_annual_release_de', parser_version='1', parse_status='partial',
        source=SOURCE, metrics=[dict(metric_key=k, display_name=v[0], category='income', value_type='decimal',
            value_semantics=v[1], dimension_key='monetary', status='active') for k,v in sorted(METRICS.items())],
        units=[dict(unit_key='EUR_MILLION', unit_version='1', display_name='Millionen Euro', dimension_key='monetary',
            monetary_currency_code='EUR', scale_numerator='1000000', scale_denominator='1', status='frozen')],
        observations=candidates)
