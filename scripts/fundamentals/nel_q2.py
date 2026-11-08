"""NEL ASA Q2 2026 PDF adapter; five exact consolidated quarterly facts only."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from .pdf_document import read_pdf
from . import esef, pne, zeiss

URL = 'https://mb.cision.com/Public/115/4374557/96afc9701633c3dd.pdf'
ISIN = 'NO0010081235'
PUBLICATION = '2026-07-15'
PARSER = 'nel_q2_2026_pdf_v1'
VERSION = '1'
CONTENT_TYPE = 'application/pdf'
SOURCE = dict(source_key='nel_official_quarterly_reports', source_type='issuer_quarterly_report',
              display_name='NEL ASA official quarterly reports',
              base_url='https://mb.cision.com/Public/115/4374557/', enabled='0')
PERIOD = dict(start='2026-04-01', end='2026-06-30')
METRIC_ORDER = ('revenue', 'ebitda', 'ifrs_operating_profit', 'profit_after_tax', 'operating_cashflow')
DEFINITIONS = {
    'revenue': zeiss.DEFINITIONS['revenue'][:2],
    'ebitda': pne.METRICS['ebitda'],
    'ifrs_operating_profit': esef.DEFS['ifrs_operating_profit'],
    'profit_after_tax': esef.DEFS['profit_after_tax'],
    'operating_cashflow': esef.DEFS['operating_cashflow'],
}
ROW_PATTERNS = {
    'revenue': re.compile(r'\brevenue\s+from\s+contracts\s+with\s+customers\b', re.I),
    'ifrs_operating_profit': re.compile(r'\boperating\s+(?:loss|profit)\b', re.I),
    'profit_after_tax': re.compile(r'\bnet\s+income\s+\(\s*loss\s*\)\s+for\s+(?:the\s+)?period\b', re.I),
    'operating_cashflow': re.compile(r'\bnet\s+cash\s+flow\s+from\s+operating\s+activities\b', re.I),
    'ebitda': re.compile(r'^total$', re.I),
}
# Fixed single-document import: reject unexpected values instead of accepting
# a shifted Q2 column, a note number, or a different subsection's Total.
EXPECTED_Q2_VALUES = dict(revenue='153407', ebitda='-155337', ifrs_operating_profit='-205220',
                          profit_after_tax='-188571', operating_cashflow='1673')
TABLE_PATTERNS = {
    'income': re.compile(r'consolidated\s+statement\s+of\s+comprehensive\s+income', re.I),
    'cashflow': re.compile(r'consolidated\s+statement\s+of\s+cash\s+flows?', re.I),
    'segments': re.compile(r'\bthe\s+following\s+table\s+includes\s+information\s+about\s+Nel.s\s+operating\s+segments\b', re.I),
}


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _normal(text):
    return re.sub(r'\s+', ' ', text.replace('\u2212', '-').replace('\u2013', '-')).strip()


def _number(text):
    value = _normal(text).replace('\u00a0', '')
    if value in {'', '-', '—', '–', 'N/A'}:
        return None
    negative = value.startswith('-') or (value.startswith('(') and value.endswith(')'))
    if value.startswith('-'):
        value = value[1:].strip()
    elif negative:
        value = value[1:-1].strip()
    value = re.sub(r'(?<=\d)[ ,](?=\d)', '', value)
    value = value.replace(',', '')
    if not re.fullmatch(r'(?:\d+)(?:\.\d+)?', value):
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        return None
    if negative:
        result = -result
    return format(result, 'f').rstrip('0').rstrip('.') if '.' in format(result, 'f') else format(result, 'f')


def _header(line):
    words = line['words']
    pairs = []
    for index in range(len(words) - 1):
        if words[index]['text'].casefold() == 'q2' and words[index + 1]['text'] in {'2025', '2026'}:
            pairs.append((words[index + 1]['text'], (float(words[index]['x0']) + float(words[index + 1]['x1'])) / 2))
    wanted = dict(pairs)
    if '2026' not in wanted or '2025' not in wanted:
        return None
    return wanted['2026'], wanted['2025']


def _tables(pages, title_pattern, table_name):
    found = []
    for page in pages:
        lines = page['lines']
        for title_index, title_line in enumerate(lines):
            title = _normal(title_line['text'])
            if not title_pattern.search(title):
                continue
            header_index = None
            centers = None
            for candidate in range(title_index + 1, min(len(lines), title_index + 12)):
                centers = _header(lines[candidate])
                if centers:
                    header_index = candidate
                    break
            if header_index is None:
                continue
            first, second = centers
            # Exclude the Note column (where present) from the Q2 2026 value.
            left = first - 32
            middle = (first + second) / 2
            pending = []
            section = None
            for row_index in range(header_index + 1, len(lines)):
                line = lines[row_index]
                label = _normal(' '.join(w['text'] for w in line['words']
                                         if (float(w['x0']) + float(w['x1'])) / 2 < left))
                cell_words = [w['text'] for w in line['words']
                              if left <= (float(w['x0']) + float(w['x1'])) / 2 < middle]
                value = _number(' '.join(cell_words))
                if value is None:
                    if table_name == 'Note 3 Segment information':
                        heading = _normal(label)
                        if re.fullmatch(r'(?:Revenue|EBITDA|Investments(?:\s*\d+\))?|Total assets(?:\s*\d+\))?)', heading, re.I):
                            # The original note has separate Total rows for each section.
                            section = heading.casefold().split()[0]
                            pending = []
                            continue
                    if label:
                        pending.append(label)
                    continue
                full_label = _normal(' '.join(pending + [label]))
                pending = []
                found.append(dict(page=page['number'], table=table_name, row=full_label,
                                   column='Q2 2026', value=value,
                                   x0=min((float(w['x0']) for w in line['words']), default=0.0),
                                   y0=float(line['bottom']), section=section))
    return found


def _select(rows, metric):
    if metric == 'ebitda':
        matches = [row for row in rows if row.get('section') == 'ebitda'
                   and ROW_PATTERNS[metric].fullmatch(_normal(row['row']))]
    else:
        matches = [row for row in rows if ROW_PATTERNS[metric].search(re.sub(r'^\d+\s+', '', row['row']))]
    _need(len(matches) == 1, 'NEL_' + metric.upper() + '_AMBIGUOUS')
    return matches[0]


def _fact(metric, row, index, observed_at):
    position = (f'pdf:page={row["page"]};table={row["table"]};row={row["row"][:220]};'
                f'column={row["column"]};x0={row["x0"]:.2f};y0={row["y0"]:.2f}')
    return dict(metric_key=metric, value_decimal=row['value'], unit_key='NOK_THOUSAND', unit_version='1',
                period_type='fq', fiscal_year='2026', fiscal_quarter='2', period_start=PERIOD['start'],
                period_end=PERIOD['end'], estimate_horizon=None, as_of_at=None, reported_at=None,
                observed_at=observed_at, field_path=f'evidence:facts/{index};source={position}',
                value_type='decimal', dimension_key='monetary', value_text=None, value_date=None)


def parse(raw, metadata, identity):
    _need(metadata['url'] == URL and metadata['http_status'] == 200, 'NEL_RESPONSE_BINDING')
    _need(metadata['content_type'].lower().startswith(CONTENT_TYPE), 'NEL_RESPONSE_MIME')
    _need(metadata['bytes'] == len(raw) and metadata['sha256'] == hashlib.sha256(raw).hexdigest(), 'NEL_RESPONSE_HASH')
    pages = read_pdf(raw, max_bytes=16 * 1024 * 1024, max_pages=40, max_characters=1000000)
    _need(pages, 'NEL_PDF_EMPTY')
    all_text = ' '.join(page['text'] for page in pages)
    _need(re.search(r'\bNEL\s+ASA\b|Nel\s+ASA', all_text, re.I), 'NEL_DOCUMENT_IDENTITY')
    _need(re.search(r'(?:second\s+quarter|Q2)\s+(?:and\s+half[- ]year\s+)?2026', all_text, re.I), 'NEL_REPORT_PERIOD')
    _need(re.search(r'Amounts\s+in\s+NOK\s+thousands', all_text, re.I), 'NEL_UNIT')
    income = _tables(pages, TABLE_PATTERNS['income'], 'Consolidated statement of comprehensive income')
    cashflow = _tables(pages, TABLE_PATTERNS['cashflow'], 'Consolidated statement of cash flows')
    segments = _tables(pages, TABLE_PATTERNS['segments'], 'Note 3 Segment information')
    rows = {
        'revenue': _select(income, 'revenue'),
        'ifrs_operating_profit': _select(income, 'ifrs_operating_profit'),
        'profit_after_tax': _select(income, 'profit_after_tax'),
        'operating_cashflow': _select(cashflow, 'operating_cashflow'),
        'ebitda': _select(segments, 'ebitda'),
    }
    _need(all(rows[metric]['value'] == value for metric, value in EXPECTED_Q2_VALUES.items()),
          'NEL_Q2_VALUE_MISMATCH')
    _need(re.search(r'Iwatani', all_text, re.I), 'NEL_IWATANI_EVIDENCE')
    iwatani = re.search(r'.{0,140}Iwatani.{0,220}', all_text, re.I | re.S)
    special_effect = _normal(iwatani.group(0))[:512]
    observations = [_fact(metric, rows[metric], index, metadata['observed_at'])
                    for index, metric in enumerate(METRIC_ORDER)]
    facts = []
    for metric, row in zip(METRIC_ORDER, observations):
        position = row['field_path'].split(';source=', 1)[1]
        facts.append(dict(metric_key=metric, fiscal_year='2026', fiscal_quarter='2',
                          period_start=PERIOD['start'], period_end=PERIOD['end'],
                          normalized_value=row['value_decimal'], normalized_unit='NOK_THOUSAND',
                          original_value=row['value_decimal'], original_unit='NOK_THOUSAND',
                          original_currency='NOK', scale_numerator='1000', scale_denominator='1',
                          page=rows[metric]['page'], table=rows[metric]['table'], row=rows[metric]['row'][:220],
                          column='Q2 2026', position=position, source_url=URL,
                          company='NEL ASA', isin=ISIN, validation_status='qualified'))
    _need(identity['isin'] == ISIN and identity['name'] == 'NEL ASA', 'NEL_IDENTITY')
    return dict(fiscal_year_start_month=1, publication_date=PUBLICATION,
        reported_periods={'2026-Q2': dict(PERIOD)}, parser_key=PARSER, parser_version=VERSION,
        parse_status='parsed', source=SOURCE,
        metrics=[dict(metric_key=metric, display_name=DEFINITIONS[metric][0], category='cashflow' if metric == 'operating_cashflow' else 'income',
                       value_type='decimal', value_semantics=DEFINITIONS[metric][1], dimension_key='monetary', status='active')
                  for metric in METRIC_ORDER],
        units=[dict(unit_key='NOK_THOUSAND', unit_version='1', display_name='NOK thousand',
                    dimension_key='monetary', monetary_currency_code='NOK', scale_numerator='1000',
                    scale_denominator='1', status='frozen')], observations=observations,
        unqualified_metrics=[], document_evidence=[
            dict(kind='identity', pages=sorted({row['page'] for row in rows.values()})),
            dict(kind='period', value='Q2 2026', period_start=PERIOD['start'], period_end=PERIOD['end']),
            dict(kind='unit', value='Amounts in NOK thousands'),
        ], evidence_facts=facts, special_effects=[dict(topic='Iwatani settlement', excerpt=special_effect,
            treatment='evidence_only_no_ebitda_adjustment')], identity=identity)


def evidence(plan, metadata, identity):
    facts = plan.pop('evidence_facts')
    _need(len(facts) == len(plan['observations']) == 5, 'NEL_EVIDENCE_BINDING')
    for index, (fact, row) in enumerate(zip(facts, plan['observations'])):
        fact.update(metric_key=row['metric_key'], fiscal_year=row['fiscal_year'], fiscal_quarter=row['fiscal_quarter'],
                    period_start=row['period_start'], period_end=row['period_end'], normalized_value=row['value_decimal'],
                    normalized_unit=row['unit_key'], validation_status='qualified')
        row['field_path'] = f'evidence:facts/{index};source={fact["position"]}'
    doc = dict(format='mosa2-fundamental-evidence-v1', kind='derived_evidence', evidence_type='nel_q2_pdf',
               source_response=dict(metadata, retained=False), issuer=identity,
               source_classification='official_issuer_quarterly_report',
               parser=dict(key=PARSER, version=VERSION), publication_date=PUBLICATION,
               reported_periods=plan['reported_periods'], document_evidence=plan['document_evidence'],
               special_effects=plan['special_effects'], facts=facts)
    compact = json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    _need(len(compact) <= 131072, 'NEL_EVIDENCE_BOUND')
    plan['evidence_json'] = compact.decode('utf-8')
    return compact, dict(metadata, kind='derived_evidence', content_type='application/json',
                         bytes=len(compact), sha256=hashlib.sha256(compact).hexdigest())
