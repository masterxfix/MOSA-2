"""DroneShield official annual PDF: qualified Financial Highlights only; no network/SQL."""
from decimal import Decimal
import re
from . import pne, zeiss
from .pdf_document import read_pdf, highlights_tables, clean_label

URL='https://announcements.asx.com.au/asxpdf/20260225/pdf/06wq71j5jq4dtc.pdf'
ISIN='AU000000DRO2'
CONTENT_TYPE='application/pdf'
SOURCE=dict(source_key='asx_official_announcements',source_type='exchange_announcement',display_name='ASX official company announcements',base_url='https://announcements.asx.com.au/',enabled='0')
DEFINITIONS={
    'revenue':zeiss.DEFINITIONS['revenue'][:2],
    'ebitda':pne.METRICS['ebitda'],
    'ebitda_underlying':('Underlying EBITDA','Reported consolidated underlying EBITDA with issuer-defined adjustments; not unadjusted EBITDA or normalised EBITDA. Adjustments retained in source.'),
    'profit_before_tax_underlying':('Underlying Profit Before Tax','Reported consolidated underlying profit before income tax with issuer-defined adjustments; not EBIT or unadjusted PBT. Adjustments retained in source.'),
    'profit_after_tax':('Profit After Tax','Reported consolidated profit after income tax; not necessarily profit attributable to owners of the parent.'),
    'customer_cash_receipts':('Customer Cash Receipts','Reported consolidated cash receipts from customers during the period; not accrued revenue.'),
    'operating_cashflow':('Operating Cashflow','Reported consolidated net cash flow from operating activities during the period; not cash balances.'),
}
LABELS={'revenue':'revenue','ebitda':'ebitda','underlying ebitda':'ebitda_underlying',
    'underlying profit before tax':'profit_before_tax_underlying','underlying profit before tax (pbt)':'profit_before_tax_underlying',
    'profit after tax':'profit_after_tax','profit after tax (pat)':'profit_after_tax','customer cash receipts':'customer_cash_receipts',
    'operating cashflow':'operating_cashflow','operating cash flow':'operating_cashflow'}

def scale(text):
    if re.search(r'\b(?:USD|EUR|NZD|CAD)|US\$|NZ\$',text,re.I):raise ValueError('PDF_CURRENCY_CONFLICT')
    million=bool(re.search(r'(?<![A-Za-z])(?:[\d.,]+|\))\s*m\b|(?:\$|AUD)\s*m\b|\bmillion(?:s)?\b',text,re.I))
    thousand=bool(re.search(r'(?:\$|AUD)\s*(?:000|[\'’]000|k)\b|\bthousand(?:s)?\b',text,re.I))
    if million and thousand:raise ValueError('PDF_UNIT_CONFLICT')
    return 'million' if million else 'thousand' if thousand else None

def amount(cell,unit):
    cell=cell.strip().replace('\u2212','-')
    cell=re.sub(r'\s*(?:m|million|millions|k|thousand|thousands)(\)?)$',r'\1',cell,flags=re.I).strip()
    # An explicit currency symbol is accepted only after the table AUD qualification.
    cell=re.sub(r'^(\()?\s*(?:A\$|AUD\s*|\$)',r'\1',cell).strip()
    if not re.fullmatch(r'(?:-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\))',cell):return None
    negative=cell.startswith('(')
    value=Decimal(cell.strip('()').replace(',',''))
    if negative:value=-value
    if unit=='thousand':value/=Decimal(1000)
    return format(value,'f')

def parse(raw,observed_at):
    pages=read_pdf(raw)
    identity=' '.join(p['text'] for p in pages[:5])
    if not re.search(r'DroneShield\s+(?:Limited|Ltd)',identity,re.I) or not re.search(r'(?:annual\s+report\s*2025|2025\s*annual\s+report|year\s+ended\s+31\s+December\s+2025)',identity,re.I):
        raise ValueError('PDF_DOCUMENT_IDENTITY')
    if observed_at[:10]<'2026-02-25':raise ValueError('REPORT_PERIOD')
    document_text=' '.join(p['text'] for p in pages)
    if not re.search(r'\bAUD\b|A\$|Australian dollars',document_text,re.I):raise ValueError('PDF_CURRENCY_CONFLICT')
    tables=highlights_tables(pages);facts={};reasons={};evidence=[]
    for table in tables:
        header_scale=scale(table['context']);label_x=None;pending='';found=0
        for row in table['rows']:
            label=clean_label(row['label'])
            if not label and not any(row['cells'].values()):continue
            if label and not any(row['cells'].values()):
                if found:break
                pending=label;continue
            key=LABELS.get(label) or LABELS.get((pending+' '+label).strip());pending=''
            if key is None:
                if re.search(r'cash.*(?:term deposits|balance)',label):reasons['cash_and_term_deposits']='POINT_IN_TIME_UNSUPPORTED'
                if found and (re.match(r'\d|note|source',label) or (label and not any(row['cells'].values()))):break
                continue
            if label_x is None:label_x=row['x0']
            if abs(row['x0']-label_x)>12:
                reasons[key]='ROW_ALIGNMENT';continue
            row_scale=scale(row['label'])
            if header_scale and row_scale and header_scale!=row_scale:raise ValueError('PDF_UNIT_CONFLICT')
            cell_scales={scale(cell) for cell in row['cells'].values()}-{None}
            if len(cell_scales)>1:raise ValueError('PDF_UNIT_CONFLICT')
            unit=row_scale or header_scale or next(iter(cell_scales),None)
            if not unit:raise ValueError('PDF_UNIT_CONFLICT')
            found+=1
            for year,cell in row['cells'].items():
                if scale(cell) not in (None,unit):raise ValueError('PDF_UNIT_CONFLICT')
                value=amount(cell,unit)
                if value is None:
                    reasons[key]='UNQUALIFIED_VALUE_CELL';continue
                slot=(key,year)
                if slot in facts and facts[slot]['value_decimal']!=value:raise ValueError('FACT_CONFLICT')
                if slot in facts:continue
                facts[slot]=dict(metric_key=key,value_decimal=value,unit_key='AUD_MILLION',unit_version='1',period_type='fy',
                    fiscal_year=str(year),fiscal_quarter=None,period_start=f'{year}-01-01',period_end=f'{year}-12-31',
                    estimate_horizon=None,as_of_at=None,reported_at=None,observed_at=observed_at,value_type='decimal',
                    dimension_key='monetary',value_text=None,value_date=None,
                    field_path=f'pdf:page={table["page"]};table=Financial Highlights;row={key};column=FY{year};y={row["bottom"]:.2f};original-unit=AUD_{unit};publication-date=2026-02-25')
        evidence.append(dict(page=table['page'],qualified_rows=found))
    if not facts:raise ValueError('NO_QUALIFIED_FACTS')
    keys={k for k,y in facts}
    for key in DEFINITIONS:
        if key not in keys:reasons.setdefault(key,'ROW_NOT_QUALIFIED')
    return dict(fiscal_year_start_month=1,publication_date='2026-02-25',parser_key='droneshield_asx_annual_pdf',parser_version='1',
        parse_status='partial',source=SOURCE,document_evidence=evidence,
        unqualified_metrics=[dict(metric_key=k,reason=v) for k,v in sorted(reasons.items())],
        metrics=[dict(metric_key=k,display_name=DEFINITIONS[k][0],category='income' if k not in ('customer_cash_receipts','operating_cashflow') else 'cashflow',
            value_type='decimal',value_semantics=DEFINITIONS[k][1],dimension_key='monetary',status='active') for k in sorted(keys)],
        units=[dict(unit_key='AUD_MILLION',unit_version='1',display_name='Million Australian dollars',dimension_key='monetary',monetary_currency_code='AUD',
            scale_numerator='1000000',scale_denominator='1',status='frozen')],observations=list(facts.values()))
