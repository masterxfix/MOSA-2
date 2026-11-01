"""Reviewed third-party HTML report adapter; no HTTP, PDF, SQL or result constants."""
from decimal import Decimal
import re
from . import droneshield as definitions
from .html_evidence import Tables, clean

URL = 'https://financialfilings.com/filings/droneshield-limited/annual-report/2026/42833624/'
ISIN = definitions.ISIN
SOURCE = dict(source_key='financialfilings_html_reports', source_type='third_party_report',
              display_name='Financial Filings (independent third-party report reproduction)',
              base_url='https://financialfilings.com/', enabled='0')
LABELS = definitions.LABELS | {
    'operational cashflow': 'operating_cashflow', 'operational cash flow': 'operating_cashflow',
    'net cash from operating activities': 'operating_cashflow',
    'net cash flows from operating activities': 'operating_cashflow',
    'net cash provided by operating activities': 'operating_cashflow',
    'net cash used in operating activities': 'operating_cashflow',
    'net cash from/(used in) operating activities': 'operating_cashflow',
    'net cash provided by/(used in) operating activities': 'operating_cashflow',
    'net cash (used in)/from operating activities': 'operating_cashflow',
    'net cash generated from operating activities': 'operating_cashflow',
    'receipts from customers': 'customer_cash_receipts',
    'profit after income tax expense for the year': 'profit_after_tax',
    'profit/(loss) after income tax expense for the year': 'profit_after_tax',
    'profit for the year': 'profit_after_tax', 'profit/(loss) for the year': 'profit_after_tax',
    'profit after income tax': 'profit_after_tax',
}


def label(text):
    text = clean(text).lower().replace('\u2013', '-').replace('\u2212', '-')
    text = re.sub(r'\s*(?:\[\d+\]|[¹²³⁴⁵⁶⁷⁸⁹]|\*|\(\d+\))$', '', text)
    text = re.sub(r'\s*\((?:a\$|aud|\$)?\s*(?:m|million|000|thousand)\)$', '', text)
    return text.strip()


def scale(text):
    if re.search(r'\b(?:USD|EUR|CAD|NZD)\b|US\$|NZ\$', text, re.I): raise ValueError('HTML_CURRENCY_CONFLICT')
    if re.search(r'\bmillion(?:s)?\b|(?:\$|AUD|\d)\s*m\b', text, re.I): return Decimal(1000000), 'AUD million'
    if re.search(r'\bthousand(?:s)?\b|\$\s*[\'’]?000\b|\bAUD\s*[\'’]?000\b', text, re.I): return Decimal(1000), 'AUD thousand'
    if re.search(r'\$|\bAUD\b|Australian dollars', text, re.I): return Decimal(1), 'AUD'
    return None


def amount(text, unit):
    text = clean(text).replace('\u2212', '-')
    value = definitions.amount(text, 'million')
    if value is None: return None
    return format(Decimal(value) * unit[0] / Decimal(1000000), 'f')


def parse(raw, observed_at):
    parser = Tables(); parser.feed(raw.decode('utf-8', errors='strict')); parser.close()
    text = clean(' '.join(parser.text))
    if not re.search(r'DroneShield\s+(?:Limited|Ltd)', text, re.I) or not re.search(r'(?:annual\s+report\s*2025|2025\s*annual\s+report|year\s+ended\s+31\s+December\s+2025)', text, re.I):
        raise ValueError('HTML_REPORT_IDENTITY')
    if not re.search(r'\bAUD\b|Australian dollars|A\$', text, re.I): raise ValueError('HTML_CURRENCY_CONFLICT')
    if re.search(r'(?:all amounts|presented|expressed)\s+in\s+(?:US|United States|New Zealand|Canadian)\s+dollars', text, re.I): raise ValueError('HTML_CURRENCY_CONFLICT')
    if not re.search(r'(?:year\s+ended\s+31\s+December\s+2025|31\s+December\s+2025)', text, re.I): raise ValueError('REPORT_PERIOD')
    if observed_at[:10] < '2026-02-25': raise ValueError('REPORT_PERIOD')
    facts = {}; qualified_tables = 0
    for ti, table in enumerate(parser.tables, 1):
        if table['nested']: continue
        rows = table['rows']; context = table['context'] + ' ' + ' '.join(' '.join(r) for r in rows[:5])
        highlights = bool(re.search(r'financial\s+highlights', context, re.I))
        statement = bool(re.search(r'(?:consolidated\s+)?statement\s+of\s+(?:profit|comprehensive|cash\s+flows)', context, re.I))
        consolidated = bool(re.search(r'consolidated', context, re.I))
        if not highlights and not (statement and consolidated): continue
        if re.search(r'parent\s+(?:entity|company)\s+(?:statement|financial)', context, re.I): continue
        columns = None; header = None
        for ri, row in enumerate(rows[:12]):
            found = {}
            for ci, cell in enumerate(row):
                match = re.fullmatch(r'(?:FY\s*)?(202[45])(?:\s*(?:AUD|A?\$)(?:\s*[\'’]?000|\s*m)?)?', cell, re.I)
                if match:
                    year = int(match[1])
                    if year in found: found = {}; break
                    found[year] = ci
            if set(found) == {2025, 2024}:
                columns = found; header = ri; break
        if columns is None: continue
        header_text = ' '.join(' '.join(r) for r in rows[:header+3])
        header_unit = scale(header_text)
        qualified_tables += 1
        for ri, row in enumerate(rows[header+1:], header+2):
            if max(columns.values()) >= len(row): continue
            # Years map to explicit cell positions; no collapsing numeric/empty cells.
            left = ' '.join(row[:min(columns.values())])
            metric_label = label(re.sub(r'\s+\d+$', '', left))
            key = LABELS.get(metric_label)
            if not key: continue
            if not highlights and key not in ('revenue','profit_after_tax','operating_cashflow','customer_cash_receipts'): continue
            # A statement qualifies the more precise accounting amount; highlights are fallback.
            priority = 2 if statement and consolidated else 1
            pair = []
            for year, ci in columns.items():
                cell = row[ci]
                cell_unit = scale(cell)
                # Bare '$' identifies currency, not a change from table millions/thousands.
                unit = (cell_unit if cell_unit and cell_unit[0] != 1 else None) or scale(left) or header_unit or cell_unit
                if unit is None: continue
                value = amount(cell, unit)
                if value is None: continue
                position = f'html:table={ti};row={ri};column={ci+1}'
                pair.append(((key, year), dict(value=value, priority=priority,
                    evidence=dict(original_label=left, original_value=cell, original_unit=unit[1], position=position,
                                  table_class='consolidated_statement' if priority == 2 else 'financial_highlights'))))
            # A comparison is imported only with two unambiguous annual columns.
            if len(pair) != 2: continue
            for slot, fact in pair:
                old = facts.get(slot)
                if old and old['priority'] == fact['priority'] and Decimal(old['value']) != Decimal(fact['value']): raise ValueError('FACT_CONFLICT')
                if not old or fact['priority'] > old['priority']: facts[slot] = fact
    if not facts: raise ValueError('NO_QUALIFIED_FACTS')
    keys = sorted({k for k,y in facts}); observations = []; evidence = []
    for (key,year), fact in sorted(facts.items()):
        observations.append(dict(metric_key=key,value_decimal=fact['value'],unit_key='AUD_MILLION',unit_version='1',period_type='fy',
            fiscal_year=str(year),fiscal_quarter=None,period_start=f'{year}-01-01',period_end=f'{year}-12-31',estimate_horizon=None,
            as_of_at=None,reported_at=None,observed_at=observed_at,value_type='decimal',dimension_key='monetary',value_text=None,value_date=None,
            field_path=fact['evidence']['position']))
        evidence.append(fact['evidence'])
    return dict(fiscal_year_start_month=1,publication_date='2026-02-25',parser_key='financialfilings_annual_html',parser_version='1',
        parse_status='partial',source=SOURCE,evidence_facts=evidence,document_evidence=dict(qualified_tables=qualified_tables),
        unqualified_metrics=[dict(metric_key=k,reason='ROW_NOT_QUALIFIED') for k in sorted(set(definitions.DEFINITIONS)-set(keys))],
        metrics=[dict(metric_key=k,display_name=definitions.DEFINITIONS[k][0],category='cashflow' if k in ('customer_cash_receipts','operating_cashflow') else 'income',
            value_type='decimal',value_semantics=definitions.DEFINITIONS[k][1],dimension_key='monetary',status='active') for k in keys],
        units=[dict(unit_key='AUD_MILLION',unit_version='1',display_name='Million Australian dollars',dimension_key='monetary',monetary_currency_code='AUD',
            scale_numerator='1000000',scale_denominator='1',status='frozen')],observations=observations)
