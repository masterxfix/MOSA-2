"""Versioned PNE Q1 release qualification; original text is the only value source."""
import re
from . import pne, zeiss

URL = 'https://www.pnegroup.com/newsroom/einzelansicht/quartalsergebnis-pne-ag-startet-gut-in-das-jahr-2026/'
ISIN = pne.ISIN
SOURCE = pne.SOURCE
PUBLICATION = '2026-05-13'
LABELS = {
    'total_output': r'\bGesamtleistung\b',
    'revenue': r'\b(?:Umsatzerlöse|Umsatz|Umsätze)\b',
    'ebitda_normalised': r'(?:um Sondereffekte bereinigte[ns]? EBITDA(?:\s*\([^)]*normalis(?:ed|iert)[^)]*\))?|normalisierte[ns]? EBITDA(?:\s*\([^)]*normalised EBITDA[^)]*\))?|normalised EBITDA)',
    'ebit': r'\bEBIT(?![-\w])',
}
DEFINITIONS = {k:pne.METRICS[k] for k in LABELS if k in pne.METRICS}
DEFINITIONS['revenue'] = zeiss.DEFINITIONS['revenue'][:2]
AMOUNT = re.compile(r'(?<![\d.,+−-])('+pne.NUMBER+r')\s*(Mio\.?\s*(?:Euro|EUR|€)|Millionen\s*(?:Euro|EUR|€)|Mrd\.?\s*(?:Euro|EUR|€)|(?:Euro|EUR|€))(?!\w)')
# Do not split decimals or the abbreviation Mio.; retain global evidence offsets.
SENTENCE = re.compile(r'.+?(?:[.!?](?=\s+[A-ZÄÖÜ„“"])(?<!Mio\.)(?<!Mrd\.)|$)')
FORECAST = re.compile(r'Prognose|Guidance|Ausblick|erwartet|erwarten|rechnet|Gesamtjahr|gesamte[nms]? Jahr|Geschäftsjahr|voraussichtlich',re.I)

def parse(raw, observed_at):
    text = pne.normalized_text(raw)
    heads = list(re.finditer(r'Cuxhaven,\s*13\.\s*Mai\s*2026\s*[–—-]',text))
    if len(heads)!=1 or 'PNE AG' not in text or not re.search(r'(?:ersten?s? Quartal\s*(?:des Jahres\s*)?2026|Q1\s*2026|ersten drei Monaten(?: des Jahres)?\s*2026)',text,re.I):
        raise ValueError('QUARTER_IDENTITY')
    if PUBLICATION>observed_at[:10]:raise ValueError('REPORT_PERIOD')
    start=heads[0].end()
    endmatch=re.search(r'Über (?:die )?PNE|Kontakt:|Pressekontakt',text[start:])
    end=start+endmatch.start() if endmatch else len(text)
    facts={};unqualified=[]
    for sentence in SENTENCE.finditer(text,start,end):
        content=sentence.group()
        if FORECAST.search(content):continue
        labels=[k for k,p in LABELS.items() if re.search(p,content,re.I)]
        if len(labels)!=1:continue
        key=labels[0]
        # Exclude specific other periods and retain all such prose in the raw archive.
        if re.search(r'Halbjahr|zweiten|dritten|vierten|Q[234]|2024|2027',content,re.I):continue
        amounts=list(AMOUNT.finditer(content))
        if not amounts:continue
        if any(not re.fullmatch(r'(?:Mio\.?|Millionen)\s*(?:Euro|EUR|€)',a[2]) for a in amounts):
            raise ValueError('UNIT_CONFLICT')
        # Current result first, optional explicitly labelled prior Q1 result second.
        prior=re.search(r'Vorjahr(?:esquartal)?\s*:|Q1\s*2025\s*:|(?:erstes|ersten) Quartal 2025\s*:',content,re.I)
        if len(amounts)>2 or (len(amounts)==2 and (prior is None or not amounts[0].end()<=prior.start()<amounts[1].start())):continue
        if len(amounts)==1 and (prior or re.search(r'2025',content)):continue
        if re.search(r'2025',content[:amounts[0].end()]):raise ValueError('PERIOD_CONFLICT')
        for index,amount in enumerate(amounts):
            year=2026-index;value=pne.number(amount[1]);slot=(key,year)
            if slot in facts and facts[slot]['value_decimal']!=value:raise ValueError('FACT_CONFLICT')
            a=sentence.start()+amount.start(1);b=sentence.start()+amount.end(1)
            facts[slot]=dict(metric_key=key,value_decimal=value,unit_key='EUR_MILLION',unit_version='1',
                period_type='fq',fiscal_year=str(year),fiscal_quarter='1',period_start=f'{year}-01-01',period_end=f'{year}-03-31',
                estimate_horizon=None,as_of_at=None,reported_at=None,observed_at=observed_at,
                field_path=f'html-text-v1:{a}:{b};publication-date={PUBLICATION};date-only;PNE-calendar-Q1',
                value_type='decimal',dimension_key='monetary',value_text=None,value_date=None)
    if not facts:raise ValueError('NO_QUALIFIED_FACTS')
    keys={k for k,y in facts}
    for key in LABELS:
        if key not in keys:unqualified.append(dict(metric_key=key,reason='NO_UNAMBIGUOUS_Q1_ACTUAL'))
    return dict(fiscal_year_start_month=1,publication_date=PUBLICATION,parser_key='pne_quarter_release_de',parser_version='1',
        parse_status='partial',source=SOURCE,unqualified_metrics=unqualified,
        metrics=[dict(metric_key=k,display_name=DEFINITIONS[k][0],category='income',value_type='decimal',
            value_semantics=DEFINITIONS[k][1],dimension_key='monetary',status='active') for k in sorted(keys)],
        units=[dict(unit_key='EUR_MILLION',unit_version='1',display_name='Millionen Euro',dimension_key='monetary',
            monetary_currency_code='EUR',scale_numerator='1000000',scale_denominator='1',status='frozen')],
        observations=list(facts.values()))
