"""Bounded, profile-driven HKEX annual-report adapter; no SQL or transport."""
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from pathlib import Path

from .pdf_document import read_pdf
from . import zeiss

PARSER = 'hkex_consolidated_annual_pdf_v1'
VERSION = '1'
CONTENT_TYPE = 'application/pdf'
MAX_BYTES = 40 * 1024 * 1024
MAX_PAGES = 450
MAX_CHARACTERS = 6000000
SOURCE = dict(source_key='hkex_official_annual_reports', source_type='exchange_annual_report',
              display_name='Hong Kong Exchanges and Clearing official annual reports',
              base_url='https://www1.hkexnews.hk/listedco/listconews/sehk/', enabled='0')

DEFINITIONS = {
    'revenue': zeiss.DEFINITIONS['revenue'][:2],
    'operating_profit': ('Operating Profit / Loss',
                         'Reported consolidated operating profit or loss explicitly titled by the issuer; not inferred EBIT.'),
    'profit_before_tax': ('Profit Before Tax',
                          'Reported consolidated total profit or loss before income tax; mapped only from the explicit ASBE total-profit row.'),
    'profit_after_tax': ('Profit After Tax',
                         'Reported consolidated net profit or loss after income tax; not profit attributable to owners only.'),
    'operating_cashflow': ('Operating Cashflow',
                           'Reported consolidated net cash flow from operating activities; not cash balances.'),
}

ROWS = {
    'revenue': re.compile(r'\b(?:operating\s+revenue|revenue)\b', re.I),
    'operating_profit': re.compile(r'\boperating\s+(?:profit|loss)\b', re.I),
    'profit_before_tax': re.compile(r'\btotal\s+(?:profit|loss)\b', re.I),
    'profit_after_tax': re.compile(r'\bnet\s+(?:profit|loss)\b(?!\s+from\s+continuing|\s+attributable)', re.I),
    'operating_cashflow': re.compile(r'\bnet\s+cash\s+flows?\s+(?:from|used\s+in)\s+operating\s+activities\b', re.I),
}


def _profiles():
    return json.loads((Path(__file__).with_name('hkex_profiles.json')).read_text(encoding='utf-8'))


PROFILES = _profiles()


def profile_for(key):
    for profile in PROFILES:
        if profile['profile_key'] == key:
            return profile
    raise ValueError('HKEX_PROFILE')


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _normal(text):
    text = text.replace('\u2019', "'").replace('\u2018', "'").replace('\u2212', '-')
    return re.sub(r'\s+', ' ', text).strip()


def _identity_selector(profile):
    patterns = [re.compile(p, re.I) for p in profile['identity_patterns'] + profile['standard_patterns'] + profile['consolidation_patterns'] + profile['title_patterns']]
    def selected(number, text):
        if number <= 5:
            return True
        return any(p.search(text) for p in patterns)
    return selected


def _line_data(page):
    return page['lines']


def _numeric(value):
    value = _normal(value).replace(',', '')
    if value in {'', '–', '-', '—', 'N/A', 'n/a'}:
        return None
    negative = value.startswith('(') and value.endswith(')')
    if negative:
        value = value[1:-1].strip()
    if not re.fullmatch(r'(?:\d+)(?:\.\d+)?', value):
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    if negative:
        amount = -amount
    return format(amount, 'f')


def _header(lines, title_index, profile):
    for index in range(title_index + 1, min(len(lines), title_index + 10)):
        words = lines[index]['words']
        years = [w for w in words if re.fullmatch(r'20(?:24|25)', w['text'])]
        if len(years) < 2:
            continue
        years.sort(key=lambda w: w['x0'])
        if [w['text'] for w in years[:2]] != ['2025', '2024']:
            raise ValueError('HKEX_YEAR_COLUMNS')
        # UBTECH has Company columns after the first Consolidated pair.  The
        # first two year columns are always the consolidated statement.
        centers = [(float(w['x0']) + float(w['x1'])) / 2 for w in years]
        return index, years, centers[:2]
    raise ValueError('HKEX_YEAR_COLUMNS')


def _cells(line, centers):
    if len(centers) == 2:
        boundaries = [centers[0] - 40, (centers[0] + centers[1]) / 2, centers[1] + 40]
    else:
        boundaries = [centers[0] - 40, (centers[0] + centers[1]) / 2, centers[1] + 40]
    out=[]
    for left, right in zip(boundaries, boundaries[1:]):
        words=[w['text'] for w in line['words'] if left <= (float(w['x0']) + float(w['x1'])) / 2 < right]
        out.append(' '.join(words).strip())
    return out


def _label(line, centers):
    cutoff = centers[0] - 40
    return ' '.join(w['text'] for w in line['words'] if (float(w['x0']) + float(w['x1'])) / 2 < cutoff).strip()


def _table_rows(pages, title_patterns, table_name):
    candidates=[]
    for page in pages:
        lines=_line_data(page)
        for title_index, line in enumerate(lines):
            title=_normal(line['text'])
            if not any(re.search(pattern, title, re.I) for pattern in title_patterns):
                continue
            # Ignore table-of-contents rows such as "144 Consolidated ...".
            if re.match(r'^\d+\s+', title):
                continue
            header_index, years, centers = _header(lines, title_index, None)
            pending=[]
            for row_index in range(header_index + 1, len(lines)):
                line=lines[row_index]
                label=_label(line, centers)
                cells=_cells(line, centers)
                values=[_numeric(cell) for cell in cells]
                if all(value is not None for value in values):
                    full_label=_normal(' '.join(pending + [label]))
                    pending=[]
                    candidates.append(dict(page=page['number'], table=table_name, row=full_label,
                                            row_index=row_index, cells=cells, values=values,
                                            x0=min((float(w['x0']) for w in line['words']), default=0.0),
                                            y0=float(line['bottom'])))
                elif label:
                    pending.append(label)
            # A title is sufficient; continuation pages are separate titled
            # tables and are therefore inspected independently.
    return candidates


def _find_fact(rows, metric):
    matches=[row for row in rows if ROWS[metric].search(row['row'])]
    if len(matches) != 1:
        raise ValueError('HKEX_' + metric.upper() + '_AMBIGUOUS')
    return matches[0]


def _unit_context(pages):
    texts=' '.join(page['text'] for page in pages)
    matches=re.findall(r'RMB[\s\u2018\u2019\'’]*000|RMB\s*million', texts, re.I)
    if not matches or any('million' in m.casefold() for m in matches):
        raise ValueError('HKEX_UNIT')
    return 'RMB’000', 'CNY_THOUSAND', '1000', '1'


def _anchor(pages, patterns, code):
    for page in pages:
        for pattern in patterns:
            match=re.search(pattern, page['text'], re.I)
            if match:
                excerpt=' '.join(page['text'].split())
                start=max(0, match.start()-80)
                return dict(page=page['number'], pattern=pattern, excerpt=excerpt[start:start+360])
    raise ValueError(code)


def _fact(metric, row, year, profile, unit_key, original_unit, scale_numerator, scale_denominator, table):
    value=row['values'][0 if year == 2025 else 1]
    original=row['cells'][0 if year == 2025 else 1]
    column=f'FY{year}'
    position=(f"pdf:page={row['page']};table={table};row={row['row'][:220]};column={column};"
              f"x0={row['x0']:.2f};y0={row['y0']:.2f}")
    return dict(metric_key=metric, fiscal_year=str(year), period_start=f'{year}-01-01', period_end=f'{year}-12-31',
                normalized_value=value, normalized_unit=unit_key, original_value=original,
                original_unit=original_unit, original_currency='CNY', scale_numerator=scale_numerator,
                scale_denominator=scale_denominator, page=row['page'], table=table, row=row['row'][:220],
                column=column, position=position, source_url=profile['url'], company=profile['name'],
                isin=profile['isin'], reporting_standard=profile['standard'], consolidation_status='consolidated',
                validation_status='qualified')


def parse(raw, metadata, profile):
    _need(profile in PROFILES, 'HKEX_PROFILE')
    _need(metadata['url'] == profile['url'] and metadata['http_status'] == 200, 'HKEX_RESPONSE_BINDING')
    _need(metadata['content_type'].lower().startswith(CONTENT_TYPE), 'HKEX_RESPONSE_MIME')
    _need(metadata['bytes'] == len(raw) and metadata['sha256'] == hashlib.sha256(raw).hexdigest(), 'HKEX_RESPONSE_HASH')
    pages=read_pdf(raw, max_bytes=MAX_BYTES, max_pages=MAX_PAGES, max_characters=MAX_CHARACTERS,
                   page_selector=_identity_selector(profile))
    _need(pages and any(profile['name'].casefold() in page['text'].casefold() for page in pages[:5]), 'HKEX_IDENTITY')
    all_text=' '.join(page['text'] for page in pages)
    _need(re.search(r'Annual Report\s+2025|2025\s+annual report|年報', all_text, re.I), 'HKEX_REPORT_YEAR')
    _need(re.search(r'31 December 2025|December 31, 2025|2025-12-31', all_text, re.I), 'HKEX_REPORT_END')
    standard=_anchor(pages, profile['standard_patterns'], 'HKEX_STANDARD')
    consolidation=_anchor(pages, profile['consolidation_patterns'], 'HKEX_CONSOLIDATION')
    period=_anchor(pages, [r'31 December 2025', r'December 31, 2025'], 'HKEX_PERIOD')
    original_unit, unit_key, scale_numerator, scale_denominator = _unit_context(pages)
    income=_table_rows(pages, profile['title_patterns'][:1], 'Consolidated Income Statement')
    cash=_table_rows(pages, profile['title_patterns'][1:], 'Consolidated Cash Flow Statement')
    observations=[];facts=[]
    for table_rows, metric in [(income,'revenue'),(income,'operating_profit'),(income,'profit_before_tax'),(income,'profit_after_tax'),(cash,'operating_cashflow')]:
        row=_find_fact(table_rows, metric)
        for year in (2025, 2024):
            fact=_fact(metric,row,year,profile,unit_key,original_unit,scale_numerator,scale_denominator,
                       'Consolidated Income Statement' if table_rows is income else 'Consolidated Cash Flow Statement')
            i=len(facts);facts.append(fact)
            observations.append(dict(metric_key=metric,value_decimal=fact['normalized_value'],unit_key=unit_key,unit_version='1',
                period_type='fy',fiscal_year=str(year),fiscal_quarter=None,period_start=fact['period_start'],
                period_end=fact['period_end'],estimate_horizon=None,as_of_at=None,reported_at=None,
                observed_at=metadata['observed_at'],field_path=f'evidence:facts/{i};source={fact["position"]}',
                value_type='decimal',dimension_key='monetary',value_text=None,value_date=None))
    periods={'2024':dict(start='2024-01-01',end='2024-12-31'), '2025':dict(start='2025-01-01',end='2025-12-31')}
    metrics=[dict(metric_key=k,display_name=DEFINITIONS[k][0],category='cashflow' if k=='operating_cashflow' else 'income',
                  value_type='decimal',value_semantics=DEFINITIONS[k][1],dimension_key='monetary',status='active')
             for k in ('revenue','operating_profit','profit_before_tax','profit_after_tax','operating_cashflow')]
    doc=dict(format='mosa2-fundamental-evidence-v1',kind='derived_evidence',evidence_type='hkex_pdf',
             source_response=dict(metadata,retained=False),issuer=dict(isin=profile['isin'],name=profile['name']),
             identity_mapping=profile,source_classification='official_hkex_annual_report',
             parser=dict(key=PARSER,version=VERSION),
             reporting_standard=profile['standard'],consolidation_status='consolidated',
             reported_periods=periods,identity_evidence=[dict(page=page['number'],excerpt=' '.join(page['text'].split())[:360]) for page in pages[:2]],
             standard_evidence=[standard],consolidation_evidence=[consolidation],period_evidence=[period],
             facts=facts,gaps=[])
    compact=json.dumps(doc,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    _need(len(compact)<=131072, 'HKEX_EVIDENCE_BOUND')
    plan=dict(fiscal_year_start_month=1,parser_key=PARSER,parser_version=VERSION,parse_status='parsed',source=SOURCE,
              metrics=metrics,units=[dict(unit_key=unit_key,unit_version='1',display_name='CNY thousand (RMB’000)',
                  dimension_key='monetary',monetary_currency_code='CNY',scale_numerator=scale_numerator,
                  scale_denominator=scale_denominator,status='frozen')],observations=observations,
              unqualified_metrics=[],metadata=metadata,evidence_json=compact.decode('utf-8'),
              stored_evidence=dict(metadata,kind='derived_evidence',content_type='application/json',bytes=len(compact),
                                   sha256=hashlib.sha256(compact).hexdigest()),archive=None,
              identity=dict(isin=profile['isin'],name=profile['name']),hkex_profile=profile,
              reported_periods=periods)
    return plan
