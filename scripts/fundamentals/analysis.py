"""On-demand deterministic AI input. No model, provider or persistence."""
from decimal import Decimal as D, InvalidOperation
from datetime import date, timedelta
IMPORTANT=('revenue','ebit','ebitda','profit_after_tax','operating_cashflow')
class SnapshotError(ValueError):
    pass

SNAPSHOT_CODES={'CURRENT_SHAPE','CURRENT_REFERENCE','FACT_SHAPE','PERIOD_INVALID','DECIMAL_INVALID','SOURCE_REFERENCE','SNAPSHOT_VALIDATION_FAILED'}

def validate_input(asset,sources):
    if not isinstance(asset,dict):raise SnapshotError('FACT_SHAPE')
    if type(asset.get('current')) is not dict:raise SnapshotError('CURRENT_SHAPE')
    facts=asset.get('facts')
    if type(facts) is not list or not all(type(r) is dict for r in facts):raise SnapshotError('FACT_SHAPE')
    if type(sources) is not list or not all(type(s) is dict and 'id' in s and 'source_type' in s for s in sources):raise SnapshotError('SOURCE_REFERENCE')
    ids=set();source_ids={str(s['id']) for s in sources}
    required={'id','metric_key','value_decimal','unit_key','unit_version','period_type','fiscal_year','fiscal_quarter','period_start','period_end','source_id','fetch_id','field_path','evidence_sha256','parser_key','parse_status','monetary_currency_code','scale_numerator','scale_denominator'}
    for r in facts:
        if not required<=r.keys() or str(r['id']) in ids:raise SnapshotError('FACT_SHAPE')
        ids.add(str(r['id']))
        if str(r['source_id']) not in source_ids or not r['fetch_id'] or not r['field_path'] or not isinstance(r['evidence_sha256'],str) or len(r['evidence_sha256'])!=64:raise SnapshotError('SOURCE_REFERENCE')
        try:
            start=date.fromisoformat(r['period_start']);end=date.fromisoformat(r['period_end'])
            if start>=end or r['period_type'] not in ('fy','fq') or abs(int(r['fiscal_year'])-end.year)>1:raise ValueError()
            if r['period_type']=='fy' and r['fiscal_quarter'] is not None:raise ValueError()
            if r['period_type']=='fq' and str(r['fiscal_quarter']) not in ('1','2','3','4'):raise ValueError()
        except (ValueError,TypeError):raise SnapshotError('PERIOD_INVALID') from None
        try:
            for k in ('value_decimal','scale_numerator','scale_denominator'):
                if not isinstance(r[k],str) or not D(r[k]).is_finite():raise InvalidOperation()
            if D(r['scale_numerator'])<=0 or D(r['scale_denominator'])<=0:raise InvalidOperation()
        except (InvalidOperation,ValueError,TypeError):raise SnapshotError('DECIMAL_INVALID') from None
    for slot,rows in asset['current'].items():
        if not isinstance(slot,str) or type(rows) is not list or len(rows)!=1 or type(rows[0]) is not dict or 'observation_id' not in rows[0]:raise SnapshotError('CURRENT_SHAPE')

def build(asset,sources):
    try:
        validate_input(asset,sources)
        return _build(asset,sources)
    except SnapshotError:raise
    except (KeyError,TypeError,ValueError,AttributeError,InvalidOperation):raise SnapshotError('SNAPSHOT_VALIDATION_FAILED') from None

def _build(asset,sources):
    facts=asset['facts']; byid={str(r['id']):r for r in facts}
    current=[]
    for slot,rows in asset['current'].items():
        for c in rows:
            if str(c['observation_id']) not in byid:raise SnapshotError('CURRENT_REFERENCE')
            r=byid[str(c['observation_id'])]
            if slot!=r['metric_key']+':'+r['period_type']:raise SnapshotError('CURRENT_REFERENCE')
            current.append(str(c['observation_id']))
    source_ids={str(r['source_id']) for r in facts}
    out=dict(contract='mosa2-ai-analysis-input-v1',identity=dict(id=asset['id'],name=asset['name'],isin=[x['normalized_value'] for x in asset['identifiers']]),
        facts=[],calculations=[],interpretations=[],current_observation_ids=current,
        sources=[s for s in sources if str(s['id']) in source_ids],market_source_ids=[str(s['source_id']) for s in asset['market_sources']],
        missing_metrics=sorted(set(IMPORTANT)-{r['metric_key'] for r in facts}),warnings=[],periods=sorted({r['period_start']+'/'+r['period_end'] for r in facts}))
    groups={}
    for r in facts:
        curated=r['parser_key']=='curated_public_facts_v1'
        if D(r['value_decimal'])<0:out['warnings'].append(dict(code='NEGATIVE_VALUE',observation_ids=[str(r['id'])]))
        out['facts'].append(dict(observation_id=str(r['id']),metric=r['metric_key'],value=r['value_decimal'],unit=r['unit_key'],currency=r['monetary_currency_code'],period_type=r['period_type'],start=r['period_start'],end=r['period_end'],source_id=str(r['source_id']),fetch_id=str(r['fetch_id']),field_path=r['field_path'],evidence_sha256=r['evidence_sha256'],origin='manually_reviewed_public_facts' if curated else next((s['source_type'] for s in sources if str(s['id'])==str(r['source_id'])),'unknown'),rounded=True if curated else None,parser_status=r['parse_status']))
        # Exact source/unit/calendar/quarter cohorts; FY cannot mix with FQ.
        start=date.fromisoformat(r['period_start']);end=date.fromisoformat(r['period_end'])
        k=(r['metric_key'],r['period_type'],str(r['fiscal_quarter']),r['unit_key'],str(r['unit_version']),str(r['source_id']),*([] if r['period_type']=='fy' else [start.month,start.day,end.month,end.day]))
        groups.setdefault(k,[]).append(r)
    def calc(kind,rows,value,**extra):
        out['calculations'].append(dict(kind=kind,observation_ids=[str(r['id']) for r in rows],value=format(value,'f'),**extra))
    for rows in groups.values():
        rows=sorted(rows,key=lambda r:r['period_end'])
        for a,b in zip(rows,rows[1:]):
            if int(b['fiscal_year'])-int(a['fiscal_year'])!=1:continue
            if a['period_end']==b['period_end']:raise SnapshotError('PERIOD_INVALID')
            sa,ea,sb,eb=(date.fromisoformat(r[k]) for r,k in [(a,'period_start'),(a,'period_end'),(b,'period_start'),(b,'period_end')])
            same_calendar=(sa.month,sa.day,ea.month,ea.day)==(sb.month,sb.day,eb.month,eb.day)
            week_years=a['period_type']=='fy' and all((e-s).days+1 in (364,371) for s,e in [(sa,ea),(sb,eb)]) and sb==ea+timedelta(days=1)
            if not (same_calendar or week_years):continue
            av,bv=D(a['value_decimal']),D(b['value_decimal'])
            calc('absolute_change',[a,b],bv-av,unit=a['unit_key'])
            if av>0:calc('growth_percent',[a,b],(bv/av-1)*100)
            else:out['warnings'].append(dict(code='NONPOSITIVE_BASE_NO_GROWTH_PERCENT',observation_ids=[str(a['id']),str(b['id'])]))
            if av<0<=bv:out['warnings'].append(dict(code='LOSS_TO_NONNEGATIVE',observation_ids=[str(a['id']),str(b['id'])]))
    def compatible(a,b):
        return all(str(a[k])==str(b[k]) for k in ('period_type','period_start','period_end','monetary_currency_code','source_id'))
    def base(r):return D(r['value_decimal'])*D(r['scale_numerator'])/D(r['scale_denominator'])
    for a in facts:
        if a['metric_key'] in ('ebit','ebitda','ebitda_underlying'):
            matches=[b for b in facts if b['metric_key']=='revenue' and compatible(a,b)]
            if len(matches)==1 and base(matches[0])>0:calc('margin_percent',[a,matches[0]],base(a)/base(matches[0])*100)
        if a['metric_key'] in ('ebitda_underlying','ebitda_normalised'):
            matches=[b for b in facts if b['metric_key']=='ebitda' and compatible(a,b) and a['unit_key']==b['unit_key']]
            if len(matches)==1:calc('adjustment_gap',[a,matches[0]],D(a['value_decimal'])-D(matches[0]['value_decimal']),unit=a['unit_key'])
    if not facts:out['warnings'].append(dict(code='NO_QUALIFIED_FUNDAMENTALS'))
    if any(f['rounded'] for f in out['facts']):out['warnings'].append(dict(code='CURATED_ROUNDED_USER_REVIEW_NOT_RUNNER_FETCH'))
    return out
