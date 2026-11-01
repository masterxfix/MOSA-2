"""SEC Company Facts -> existing writer plan. Pure Decimal parsing; no I/O.

FY is the filing's label, never a calendar-year guess. A current-period 10-K
anchor proves each requested FY; comparative rows never establish FY labels.
Conflicting repeated or amended facts stop, rather than silently restate Current.
"""
from datetime import date
from decimal import Decimal
import hashlib
import json
import re
from .zeiss import DEFINITIONS

PARSER = 'sec_companyfacts_us_gaap_v1'
SOURCE = dict(source_key='sec_edgar_companyfacts', source_type='regulator_xbrl',
              display_name='SEC EDGAR XBRL Company Facts', base_url='https://data.sec.gov/', enabled='0')
# No synonym/fallback tags: each tag retains its exact accounting meaning.
TAGS = {
    'RevenueFromContractWithCustomerExcludingAssessedTax': 'revenue',
    'OperatingIncomeLoss': 'operating_income',
    'NetIncomeLoss': 'profit_attributable_to_owners',
    'ProfitLoss': 'profit_after_tax',
    'NetCashProvidedByUsedInOperatingActivities': 'operating_cashflow',
}
DEFS = {k: DEFINITIONS[k][:2] for k in ('revenue', 'profit_attributable_to_owners')}
DEFS.update(
    operating_income=('Operating Income / Loss', 'Reported consolidated US-GAAP operating income or loss; not assumed equivalent to EBIT.'),
    profit_after_tax=('Profit After Tax', 'Reported consolidated profit after income tax; not necessarily profit attributable to owners of the parent.'),
    operating_cashflow=('Operating Cashflow', 'Reported consolidated net cash flow from operating activities during the period; not cash balances.'))
UNIT = dict(unit_key='USD', unit_version='1', display_name='US dollars', dimension_key='monetary',
            monetary_currency_code='USD', scale_numerator='1', scale_denominator='1', status='frozen')


def need(ok, code):
    if not ok: raise ValueError(code)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def url(cik):
    need(isinstance(cik, str) and re.fullmatch(r'[0-9]{10}', cik) is not None, 'SEC_IDENTITY')
    return 'https://data.sec.gov/api/xbrl/companyfacts/CIK'+cik+'.json'


def number(value):
    need(type(value) in (int, Decimal), 'SEC_NUMBER')
    value = format(Decimal(value), 'f')
    need(re.fullmatch(r'-?(?:0|[1-9][0-9]{0,25})(?:\.[0-9]{1,12})?', value) is not None, 'SEC_NUMBER')
    return value


def parse(raw, metadata, identity, mapping, years):
    need(type(raw) is bytes and 0 < len(raw) <= 16*1024*1024, 'SEC_BOUND')
    need(metadata['url'] == url(mapping['cik']) and metadata['http_status'] == 200
         and metadata['bytes'] == len(raw) and metadata['sha256'] == hashlib.sha256(raw).hexdigest(), 'SEC_RESPONSE_BINDING')
    need(identity['isin'] == mapping['isin'] and re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', identity['isin']) is not None
         and mapping['verification'] == 'reviewed_cik_isin' and mapping['reference'].startswith('https://www.sec.gov/Archives/edgar/data/'+str(int(mapping['cik']))+'/'), 'SEC_IDENTITY')
    need(type(years) is tuple and len(years) == 2 and all(type(y) is int for y in years) and years[1] == years[0]+1, 'SEC_YEARS')
    def unique(pairs):
        result = {}
        for k,v in pairs:
            need(k not in result, 'SEC_DUPLICATE_KEY'); result[k] = v
        return result
    def invalid(_): raise ValueError('SEC_NUMBER')
    data = json.loads(raw, parse_float=Decimal, parse_constant=invalid, object_pairs_hook=unique)
    norm = lambda s: re.sub('[^A-Z0-9]', '', s.upper())
    need(type(data['cik']) is int and data['cik'] == int(mapping['cik'])
         and norm(data['entityName']) in {norm(n) for n in mapping['sec_names']}, 'SEC_IDENTITY')
    gaap = data['facts']['us-gaap']; candidates = []; today = metadata['observed_at'][:10]
    for tag, metric in TAGS.items():
        concept = gaap.get(tag)
        if concept is None: continue
        need(isinstance(concept, dict) and isinstance(concept.get('units'), dict), 'SEC_STRUCTURE')
        values = concept['units'].get('USD', [])
        need(type(values) is list and len(values) <= 20000, 'SEC_BOUND')
        for index, row in enumerate(values):
            if row.get('form') not in ('10-K', '10-K/A') or row.get('fp') != 'FY' or 'start' not in row: continue
            start, end = date.fromisoformat(row['start']), date.fromisoformat(row['end'])
            if (end-start).days+1 not in (364,365,366,371): continue  # Never quarterly/YTD or transition periods.
            need(type(row['fy']) is int and 1900 <= row['fy'] <= 9999, 'SEC_PERIOD')
            need(start < end and end.isoformat() <= row['filed'] <= today
                 and date.fromisoformat(row['filed']).isoformat() == row['filed'], 'SEC_FILING_DATE')
            need(re.fullmatch(r'[0-9]{10}-[0-9]{2}-[0-9]{6}', row['accn']) is not None, 'SEC_ACCESSION')
            candidates.append(dict(tag=tag, metric=metric, index=index, row=row, value=number(row['val'])))
    periods = {}
    for year in years:
        own = [c for c in candidates if c['row']['fy'] == year and c['row']['form'] == '10-K']
        need(bool(own), 'SEC_FY_ANCHOR_MISSING')
        # fy/fp describe the filing, including comparative rows. Only its latest
        # annual end is the current annual reporting period.
        end = max(c['row']['end'] for c in own)
        anchors = [c for c in own if c['row']['end'] == end]
        starts = {c['row']['start'] for c in anchors}
        need(len(starts) == 1 and abs(int(end[:4])-year) <= 1, 'SEC_PERIOD_CONFLICT')
        anchor = min(anchors, key=lambda c:(c['row']['filed'], c['row']['accn'], c['tag'], c['index']))
        periods[str(year)] = dict(start=starts.pop(), end=end, anchor=reference(anchor, year))
    need(date.fromisoformat(periods[str(years[0])]['end']).toordinal()+1 == date.fromisoformat(periods[str(years[1])]['start']).toordinal(), 'SEC_PERIOD_CONTINUITY')
    observations = []; evidence = []; gaps = []
    for year in reversed(years):
        period = periods[str(year)]
        for tag, metric in TAGS.items():
            matches = [c for c in candidates if c['tag'] == tag and c['row']['start'] == period['start'] and c['row']['end'] == period['end']]
            if not matches:
                gaps.append(dict(metric=metric, fiscal_year=str(year), reason='NO_QUALIFIED_USD_ANNUAL_TAG')); continue
            need(len(matches) <= 64, 'SEC_BOUND')
            need(len({Decimal(c['value']) for c in matches}) == 1, 'SEC_CONFLICTING_FILINGS')
            # Equal facts: prefer original current-period 10-K, then earliest
            # filing/position. Keep all compact duplicate/comparative references.
            matches.sort(key=lambda c:(c['row']['fy'] != year, c['row']['form'] != '10-K', c['row']['filed'], c['row']['accn'], c['index']))
            chosen = matches[0]; row = chosen['row']; position = locator(chosen)
            i = len(observations)
            observations.append(dict(metric_key=metric, value_decimal=chosen['value'], unit_key='USD', unit_version='1',
                period_type='fy', fiscal_year=str(year), fiscal_quarter=None, period_start=period['start'], period_end=period['end'],
                estimate_horizon=None, as_of_at=None, reported_at=None, observed_at=metadata['observed_at'],
                field_path=f'evidence:facts/{i};source={position}', value_type='decimal', dimension_key='monetary', value_text=None, value_date=None))
            evidence.append(dict(metric_key=metric, fiscal_year=str(year), period_start=period['start'], period_end=period['end'],
                normalized_value=chosen['value'], normalized_unit='USD', original_value=chosen['value'], original_unit='USD',
                taxonomy='us-gaap', tag=tag, position=position, cik=mapping['cik'], source_url=metadata['url'],
                selected=reference(chosen, year), occurrences=[reference(c,year) for c in matches], validation_status='qualified'))
    need(bool(observations), 'SEC_NO_QUALIFIED_FACTS')
    keys = sorted({r['metric_key'] for r in observations})
    plan = dict(fiscal_calendar='reported_fy', reported_periods=periods, source=SOURCE,
        parser_key=PARSER, parser_version='1', parse_status='parsed', units=[UNIT],
        metrics=[dict(metric_key=k, display_name=DEFS[k][0], category='cashflow' if k=='operating_cashflow' else 'income',
                      value_type='decimal', value_semantics=DEFS[k][1], dimension_key='monetary', status='active') for k in keys],
        observations=observations, unqualified_metrics=gaps, metadata=metadata)
    doc = dict(format='mosa2-fundamental-evidence-v1', kind='derived_evidence', evidence_type='sec_companyfacts',
        source_response=dict(metadata, retained=False), issuer=identity, identity_mapping=mapping,
        source_classification='official_regulatory_filing', parser=dict(key=PARSER, version='1'),
        reported_periods=periods, facts=evidence, gaps=gaps)
    compact = encode(doc); need(len(compact) <= 131072, 'SEC_EVIDENCE_BOUND')
    plan['evidence_json'] = compact.decode('utf-8')
    plan['stored_evidence'] = dict(metadata, kind='derived_evidence', content_type='application/json', bytes=len(compact), sha256=hashlib.sha256(compact).hexdigest())
    return plan


def locator(c):
    return 'json:/facts/us-gaap/'+c['tag']+'/units/USD/'+str(c['index'])


def reference(c, year):
    r = c['row']
    return dict(position=locator(c), value=c['value'], start=r['start'], end=r['end'], filing_fy=str(r['fy']), fp=r['fp'],
        form=r['form'], accession=r['accn'], filed=r['filed'], frame=r.get('frame'),
        role='amendment' if r['form']=='10-K/A' else 'current' if r['fy']==year else 'comparative')
