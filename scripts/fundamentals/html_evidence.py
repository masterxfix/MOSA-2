"""Bounded HTML tables and compact, explicitly derived evidence; no I/O."""
from html.parser import HTMLParser
import hashlib
import json
import re


def clean(text):
    return re.sub(r'\s+', ' ', text.replace('\xa0', ' ').replace('\u200b', '')).strip()


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []; self.stack = []; self.text = []; self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'): self.skip += 1
        if self.skip: return
        if tag == 'table':
            if len(self.tables) >= 2000: raise ValueError('HTML_TABLE_BOUND')
            if self.stack: self.stack[-1]['nested'] = True
            table = dict(rows=[], context=clean(' '.join(self.text))[-1800:], cell=None, row=None, nested=False)
            self.tables.append(table); self.stack.append(table)
        elif self.stack:
            table = self.stack[-1]
            if tag == 'tr': table['row'] = []
            elif tag in ('td', 'th') and table['row'] is not None:
                span = dict(attrs).get('colspan', '1')
                if not span.isdigit() or not 1 <= int(span) <= 20: raise ValueError('HTML_COLUMN_STRUCTURE')
                table['cell'] = []; table['span'] = int(span)
                table['rowspan'] = dict(attrs).get('rowspan', '1')
            elif tag == 'br' and table['cell'] is not None: table['cell'].append(' ')

    def handle_data(self, data):
        if self.skip: return
        self.text.append(data)
        if self.stack and self.stack[-1]['cell'] is not None: self.stack[-1]['cell'].append(data)

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1); return
        if self.skip or not self.stack: return
        table = self.stack[-1]
        if tag in ('td', 'th') and table['cell'] is not None:
            value = clean(''.join(table['cell']))
            if table['rowspan'] != '1': value = '[UNQUALIFIED_ROWSPAN]'
            table['row'].extend([value] + [''] * (table['span'] - 1)); table['cell'] = None
        elif tag == 'tr' and table['row'] is not None:
            if len(table['rows']) >= 5000: raise ValueError('HTML_TABLE_BOUND')
            table['rows'].append(table['row']); table['row'] = None
        elif tag == 'table': self.stack.pop()


def evidence(plan, metadata, identity, *, official=False):
    facts = plan.pop('evidence_facts')
    if not 1 <= len(facts) == len(plan['observations']) <= 256: raise ValueError('EVIDENCE_BINDING')
    doc = dict(format='mosa2-fundamental-evidence-v1', kind='derived_evidence',
               source_response=dict(metadata, retained=False), issuer=identity,
               source_classification='independent_third_party_report_reproduction',
               verification='adapter_qualified_not_independently_verified_against_issuer',
               parser=dict(key=plan['parser_key'], version=plan['parser_version']), facts=facts)
    if official:
        doc.update(source_classification='official_issuer_release',
                   verification='reviewed_official_issuer_table')
    for i, (fact, row) in enumerate(zip(facts, plan['observations'])):
        fact.update(metric_key=row['metric_key'], period_start=row['period_start'], period_end=row['period_end'],
                    normalized_value=row['value_decimal'], normalized_unit=row['unit_key'], validation_status='qualified')
        row['field_path'] = f'evidence:facts/{i};source={fact["position"]}'
    raw = json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    if len(raw) > 131072: raise ValueError('EVIDENCE_BOUND')
    plan['evidence_json'] = raw.decode('utf-8')
    stored = dict(metadata, kind='derived_evidence', content_type='application/json', bytes=len(raw),
                  sha256=hashlib.sha256(raw).hexdigest())
    return raw, stored
