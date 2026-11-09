"""Parse explicitly profiled issuer result tables through the shared HTML evidence path."""
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from . import pne, zeiss
from .html_evidence import Tables, clean, evidence
from .sec_xbrl import DEFS

DEFINITIONS = pne.METRICS | {key: zeiss.DEFINITIONS[key][:2] for key in
    ('revenue', 'profit_before_tax', 'profit_attributable_to_owners')} | {'profit_after_tax': DEFS['profit_after_tax']}
PROFILES = json.loads(Path(__file__).with_name('issuer_table_profiles.json').read_text(encoding='utf-8'))


class IssuerTable:
    PARSE_CONTEXT = 'metadata_identity'
    CONTENT_TYPE = 'text/html'

    def __init__(self, issuer, release):
        self.issuer = issuer
        self.release = release
        self.URL = release['url']
        self.ISIN = issuer['isin']
        self.SOURCE = issuer['source']
        if urlsplit(self.URL).netloc != urlsplit(self.SOURCE['base_url']).netloc or not self.URL.startswith('https://'):
            raise ValueError('SOURCE_DOMAIN')

    def parse(self, raw, metadata, identity):
        if identity['isin'] != self.ISIN or metadata['url'] != self.URL:
            raise ValueError('ISSUER_TABLE_IDENTITY')
        parser = Tables()
        parser.feed(raw.decode('utf-8', errors='strict'))
        parser.close()
        text = clean(' '.join(parser.text))
        release = self.release
        for anchor in (self.issuer['identity_anchor'], release['title_anchor']):
            if anchor not in text:
                raise ValueError('ISSUER_TABLE_IDENTITY')
        qualified = []
        for ti, table in enumerate(parser.tables, 1):
            if table['nested'] or not table['context'].endswith(self.issuer['table_heading']):
                continue
            for ri, row in enumerate(table['rows'][:3]):
                if row and row[0] == self.issuer['unit_header'] and row.count(release['column']) == 1:
                    qualified.append((ti, table['rows'], ri, row.index(release['column'])))
        if len(qualified) != 1:
            raise ValueError('ISSUER_TABLE_STRUCTURE')
        ti, rows, ri, ci = qualified[0]
        period = release['period']
        if period[2] >= metadata['observed_at'][:10]:
            raise ValueError('ISSUER_TABLE_PERIOD')
        year = date.fromisoformat(period[1]).year
        quarter = str((date.fromisoformat(period[1]).month - 1) // 3 + 1) if period[0] == 'fq' else None
        unit = self.issuer['unit']
        records = {}
        grouping = re.escape(release['thousands_separator'])
        for line, row in enumerate(rows[ri + 1:], ri + 2):
            if not row or row[0] not in self.issuer['labels'] or ci >= len(row):
                continue
            metric = self.issuer['labels'][row[0]]
            original = row[ci].replace('\u2212', '-')
            if re.fullmatch(r'-?(?:\d+|\d{1,3}(?:' + grouping + r'\d{3})+)', original) is None:
                continue
            value = original.replace(release['thousands_separator'], '')
            if metric in records:
                raise ValueError('HISTORY_CONFLICT')
            records[metric] = (
                dict(metric_key=metric, period_type=period[0], fiscal_year=str(year), fiscal_quarter=quarter,
                     period_start=period[1], period_end=period[2], as_of_at=None, reported_at=None,
                     observed_at=metadata['observed_at'], value_decimal=value, value_type='decimal',
                     unit_key=unit['unit_key'], unit_version=unit['unit_version'], dimension_key='monetary',
                     estimate_horizon=None, value_text=None, value_date=None),
                dict(position=f'html:table={ti};row={line};column={ci + 1}', original_label=row[0],
                     original_unit=self.issuer['unit_header'], original_value=row[ci], original_period=release['column']))
        if not records:
            raise ValueError('NO_QUALIFIED_FACTS')
        return dict(source=self.SOURCE, parser_key='official_issuer_results_table_v1', parser_version='1',
                    parse_status='partial', fiscal_year_start_month=1, units=[unit],
                    metrics=[dict(metric_key=k, display_name=DEFINITIONS[k][0], value_semantics=DEFINITIONS[k][1],
                                  value_type='decimal', category='income', dimension_key='monetary', status='active')
                             for k in records],
                    observations=[row for row, _ in records.values()], evidence_facts=[fact for _, fact in records.values()])

    @staticmethod
    def evidence(plan, metadata, identity):
        return evidence(plan, metadata, identity, official=True)
