"""Qualified issuer adapter: actual consolidated results, explicit October fiscal year.

No transport, database or financial-result constants. Unqualified content stays raw.
"""
from html.parser import HTMLParser
import re
from .pne import METRICS as EXISTING_METRICS, NUMBER, number, normalized_text

URL = 'https://reports.zeiss.com/meditec-ag/2425/de/konzernlagebericht/wirtschaftsbericht/ertragslage.html'
ISIN = 'DE0005313704'
SOURCE = dict(source_key='zeiss_meditec_official_reports', source_type='issuer_annual_report',
              display_name='Carl Zeiss Meditec official reports', base_url='https://reports.zeiss.com/meditec-ag/', enabled='0')
# Exact reusable definitions for EBIT/EBITDA preserve existing catalog hashes.
DEFINITIONS = {
    'ebit': (*EXISTING_METRICS['ebit'], 'monetary'),
    'ebitda': (*EXISTING_METRICS['ebitda'], 'monetary'),
    'revenue': ('Umsatzerlöse', 'Reported consolidated revenue; not total output.', 'monetary'),
    'ebita': ('EBITA', 'Reported consolidated EBIT before amortisation and impairment from purchase price allocations; not EBITDA.', 'monetary'),
    'profit_before_tax': ('Ergebnis vor Ertragssteuern', 'Reported consolidated profit before income taxes.', 'monetary'),
    'profit_attributable_to_owners': ('Konzernergebnis der Anteilseigner', 'Reported consolidated profit attributable to owners of the parent, excluding non-controlling interests.', 'monetary'),
    'eps_basic': ('Unverwässerter Gewinn je Aktie', 'Reported basic earnings per share attributable to owners of the parent; not diluted EPS.', 'monetary_per_share'),
    'gross_margin': ('Bruttomarge', 'Reported consolidated gross profit as a percentage of revenue.', 'ratio'),
    'ebit_margin': ('EBIT-Marge', 'Reported consolidated EBIT as a percentage of revenue.', 'ratio'),
    'ebita_margin': ('EBITA-Marge', 'Reported consolidated EBITA as a percentage of revenue; not EBITDA margin.', 'ratio'),
    'effective_tax_rate': ('Steuerquote', 'Reported consolidated effective income tax rate, in percent.', 'ratio'),
}
ROWS = {
    'Umsatzerlöse': 'revenue', 'EBIT': 'ebit', 'EBITA': 'ebita',
    'Ergebnis vor Ertragssteuern': 'profit_before_tax',
    'Konzernergebnis nach Anteilen nicht-beherrschender Gesellschafter': 'profit_attributable_to_owners',
    'Gewinn je Aktie nach Anteilen nicht-beherrschender Gesellschafter': 'eps_basic',
    'Bruttomarge': 'gross_margin', 'EBIT-Marge': 'ebit_margin', 'EBITA-Marge': 'ebita_margin', 'Steuerquote': 'effective_tax_rate',
}

def clean(text):
    return re.sub(r'\s+', ' ', text.replace('\xad', '').replace('\u200b', '')).strip()

class Tables(HTMLParser):
    """Keep each table's row/cell state independent, in document opening order."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []; self.stack = []
    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            if self.stack and self.stack[-1]['cell'] is not None:
                # A parent cell containing a child table is not a scalar fact.
                self.stack[-1]['child_table'] = True
            rows = []; self.tables.append(rows)
            self.stack.append(dict(rows=rows,row=None,cell=None,child_table=False))
            return
        if not self.stack: return
        frame = self.stack[-1]
        if tag == 'tr': frame['row'] = []
        elif tag in ('td','th') and frame['row'] is not None:
            frame['cell'] = []; frame['child_table'] = False
    def handle_data(self, text):
        if self.stack and self.stack[-1]['cell'] is not None:
            self.stack[-1]['cell'].append(text)
    def handle_endtag(self, tag):
        if not self.stack: return
        frame = self.stack[-1]
        if tag in ('td','th') and frame['cell'] is not None:
            value = '[NESTED_TABLE_CONTENT]' if frame['child_table'] else clean(''.join(frame['cell']))
            frame['row'].append(value); frame['cell'] = None; frame['child_table'] = False
        elif tag == 'tr' and frame['row'] is not None:
            frame['rows'].append(frame['row']); frame['row'] = None; frame['cell'] = None
        elif tag == 'table': self.stack.pop()

def parse(raw, observed_at):
    text = normalized_text(raw)
    if not all(s in clean(text) for s in ('Carl Zeiss Meditec', '2024/25', '2023/24',
        'Zusammenfassung wesentlicher Größen der Konzern-Gewinn- und Verlustrechnung', 'Angaben in Mio. €')):
        raise ValueError('REPORT_IDENTITY_OR_UNITS')
    parser = Tables(); parser.feed(raw.decode('utf-8', errors='strict'))
    candidates = [(i, t) for i, t in enumerate(parser.tables) if set(ROWS).issubset({r[0] for r in t if r})]
    if len(candidates) != 1: raise ValueError('AMBIGUOUS_RESULTS_TABLE')
    table_index, table = candidates[0]
    headers = [[c for c in r if c] for r in table if '2024/25' in r or '2023/24' in r]
    if len(headers) != 1 or headers[0][:2] != ['2024/25', '2023/24']:
        raise ValueError('FISCAL_COLUMN_ORDER')
    observations = []; seen = set()
    def add(key, value, year, path):
        dimension = DEFINITIONS[key][2]
        unit = {'monetary':'EUR_MILLION', 'monetary_per_share':'EUR_PER_SHARE', 'ratio':'PERCENT'}[dimension]
        observations.append(dict(metric_key=key, value_decimal=number(value), unit_key=unit, unit_version='1',
            period_type='fy', fiscal_year=str(year), fiscal_quarter=None, period_start=f'{year-1}-10-01',
            period_end=f'{year}-09-30', estimate_horizon=None, as_of_at=None, reported_at=None,
            observed_at=observed_at, field_path=path+';FY-ending-year;October-September',
            value_type='decimal', dimension_key=dimension, value_text=None, value_date=None))
    for row_index, row in enumerate(table):
        if not row or row[0] not in ROWS: continue
        key = ROWS[row[0]]
        if key in seen: raise ValueError('DUPLICATE_METRIC')
        seen.add(key)
        cells = [(i, c) for i, c in enumerate(row) if c]
        if len(cells) != 4: raise ValueError('RESULT_COLUMNS')
        suffix = {'monetary':'', 'monetary_per_share':r'\s*€', 'ratio':r'\s*%'}[DEFINITIONS[key][2]]
        for year, (col, cell) in zip((2025, 2024), cells[1:3]):
            match = re.fullmatch('('+NUMBER+')'+suffix, cell)
            if match is None: raise ValueError('RESULT_VALUE_OR_UNIT')
            add(key, match[1], year, f'html-table-v1:{table_index}:row:{row_index}:cell:{col}')
    # EPS table must agree with the explicitly basic (unverwässert) narrative.
    eps = re.findall(r'Im Geschäftsjahr\s+2024/25 beläuft sich der unverwässerte Gewinn je Aktie des Mutterunternehmens auf ('+NUMBER+r')\s*€\s*\(Vorjahr:\s*('+NUMBER+r')\s*€\)', text)
    if len(eps) != 1 or [number(v) for v in eps[0]] != [r['value_decimal'] for r in observations if r['metric_key']=='eps_basic']:
        raise ValueError('EPS_BASIC_QUALIFICATION')
    pattern = r'Das Ergebnis vor Zinsen, Steuern und Abschreibungen\s*\(EBITDA\) betrug für das abgelaufene Geschäftsjahr\s+('+NUMBER+r')\s*Mio\.\s*€\s*\(Vorjahr:\s*('+NUMBER+r')\s*Mio\.\s*€\)'
    matches = list(re.finditer(pattern, text))
    unqualified = []
    if len(matches) == 1:
        for i, year in enumerate((2025, 2024), 1):
            add('ebitda', matches[0][i], year, f'html-text-v1:{matches[0].start(i)}:{matches[0].end(i)}')
    else:
        unqualified.append(dict(metric_key='ebitda', reason='EBITDA_PATTERN_NOT_MATCHED' if not matches else 'EBITDA_MULTIPLE_MATCHES'))
    qualified = {r['metric_key'] for r in observations}
    units = [dict(unit_key=k,unit_version='1',display_name=name,dimension_key=dim,
                  monetary_currency_code=currency,scale_numerator=scale,scale_denominator=denom,status='frozen')
        for k,name,dim,currency,scale,denom in [('EUR_MILLION','Millionen Euro','monetary','EUR','1000000','1'),
            ('EUR_PER_SHARE','Euro je Aktie','monetary_per_share','EUR','1','1'),('PERCENT','Prozent','ratio',None,'1','100')]]
    return dict(fiscal_year_start_month=10, publication_date=None, parser_key='zeiss_meditec_results_de',parser_version='3',
        unqualified_metrics=unqualified,
        parse_status='partial',source=SOURCE,units=units,observations=observations,
        metrics=[dict(metric_key=k,display_name=v[0],category='income',value_type='decimal',value_semantics=v[1],
                      dimension_key=v[2],status='active') for k,v in sorted(DEFINITIONS.items()) if k in qualified])
