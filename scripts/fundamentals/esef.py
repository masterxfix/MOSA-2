"""Bounded, offline Arelle iXBRL extraction -> shared Schema-6 plan.

Qualification of allowlisted IFRS facts, not a complete ESEF filing audit.
Arelle owns Inline transformations, contexts, units and dimensional parsing.
DTS discovery is disabled: no guessed extension semantics or network fetches.
"""
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile
from urllib.parse import urlsplit, unquote
from .sec_xbrl import encode, DEFS as SEC_DEFS
from .zeiss import DEFINITIONS

VERSION = '2.47.3'
PARSER = 'esef_ifrs_inline_v1'
MAX_ZIP = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
IFRS = re.compile(r'https?://xbrl.ifrs.org/taxonomy/20[0-9]{2}-[0-9]{2}-[0-9]{2}/ifrs-full\Z')
TAGS = {'Revenue': 'revenue', 'ProfitLossFromOperatingActivities': 'ifrs_operating_profit',
        'ProfitLossBeforeTax': 'profit_before_tax', 'ProfitLoss': 'profit_after_tax',
        'CashFlowsFromUsedInOperatingActivities': 'operating_cashflow'}
DEFS = {k: SEC_DEFS[k] for k in ('revenue', 'profit_after_tax', 'operating_cashflow')}
DEFS['profit_before_tax'] = DEFINITIONS['profit_before_tax'][:2]
# Existing operating_income explicitly means US GAAP. Do not mutate its definition.
DEFS['ifrs_operating_profit'] = ('IFRS Operating Profit / Loss',
    'Reported consolidated IFRS profit or loss from operating activities; not assumed equivalent to EBIT or EBITDA.')


def need(ok, code):
    if not ok: raise ValueError('ESEF_' + code)


def decimal(value):
    d = Decimal(value)
    need(d.is_finite(), 'NUMBER')
    text = format(d, 'f')
    if '.' in text: text = text.rstrip('0').rstrip('.')
    if text == '-0': text = '0'
    need(re.fullmatch(r'-?(?:0|[1-9][0-9]{0,25})(?:\.[0-9]{1,12})?', text), 'NUMBER')
    return text


@contextmanager
def package(raw):
    """No extractall, links, nested archives, external paths or retained reports."""
    need(0 < len(raw) <= MAX_ZIP and raw[:4] == b'PK\x03\x04', 'ZIP_BOUND')
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        entries = z.infolist()
        need(0 < len(entries) <= 2048, 'ZIP_BOUND')
        seen = set(); total = 0
        for e in entries:
            p = PurePosixPath(e.filename)
            need(e.orig_filename == e.filename and e.filename and len(e.filename) <= 220 and not p.is_absolute()
                 and all(x not in ('', '.', '..') for x in e.filename.rstrip('/').split('/'))
                 and not any(c in e.filename for c in '\\:\x00')
                 and e.filename.casefold() not in seen, 'ZIP_PATH')
            seen.add(e.filename.casefold())
            mode = e.external_attr >> 16
            need(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR) and not e.flag_bits & 1, 'ZIP_TYPE')
            total += e.file_size
            need(e.file_size <= MAX_ZIP and total <= MAX_EXPANDED
                 and e.file_size <= max(1, e.compress_size) * 250, 'ZIP_BOUND')
        with tempfile.TemporaryDirectory(prefix='mosa-esef-') as tmp:
            root = Path(tmp)
            reports = []
            for e in entries:
                if e.is_dir(): continue
                # Only the local report and taxonomy XML are needed. Images/PDFs stay in RAM ZIP.
                suffix = PurePosixPath(e.filename).suffix.lower()
                if suffix not in ('.xhtml', '.html', '.htm', '.xsd', '.xml'): continue
                body = z.read(e)  # CRC and actual decompression checked by zipfile.
                need(len(body) == e.file_size, 'ZIP_SIZE')
                no_html5 = re.sub(br'<!DOCTYPE\s+html\s*>', b'', body, flags=re.I)
                need(b'<!ENTITY' not in no_html5.upper() and b'<!DOCTYPE' not in no_html5.upper(), 'XML_DTD')
                dest = root.joinpath(*PurePosixPath(e.filename).parts)
                dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(body)
                if suffix in ('.xhtml', '.html', '.htm'):
                    reports.append((dest, e.filename, hashlib.sha256(body).hexdigest()))
            need(0 < len(reports) <= 8, 'REPORT_COUNT')
            yield root, reports
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
        raise ValueError('ESEF_ZIP_INVALID') from None
    finally:
        if 'z' in locals(): z.close()


def expanded(q):
    return '{' + q.namespaceURI + '}' + q.localName


def group_context(c):
    """Only dimensionless or explicit standard consolidated-member contexts.

    A dimensionless context additionally needs the report's tagged consolidated
    nature statement. A parent/segment/custom/typed dimension is never inferred.
    """
    if c is None or c.nonDimValues('segment') or c.nonDimValues('scenario'): return False
    for dimension, value in c.qnameDims.items():
        if not (IFRS.fullmatch(dimension.namespaceURI) and dimension.localName == 'ConsolidatedAndSeparateFinancialStatementsAxis'
                and value.isExplicit and IFRS.fullmatch(value.memberQname.namespaceURI)
                and value.memberQname.localName == 'ConsolidatedMember'): return False
    return True


def records(root, reports):
    """Arelle offline WebCache: temporary report plus pinned built-in schemas."""
    from importlib.metadata import version
    from arelle import Cntlr
    from arelle.formula.XPathContext import FunctionArgType
    from arelle.FunctionIxt import ixtFunctionNotAvailable
    from arelle.XmlValidateConst import INVALID
    need(version('arelle-release') == VERSION, 'LIBRARY_VERSION')
    out = []; issues = []
    for path, member, sha in reports:
        controller = Cntlr.Cntlr(logFileName='logToBuffer', disable_persistent_config=True)
        controller.webCache.workOffline = True
        controller.webCache.cacheDir = str(root / '.arelle-cache')
        controller.modelManager.skipDTS = True
        original = controller.webCache.getfilename
        builtin = Path(controller.webCache.builtInCacheDir).resolve()
        def local_only(url, *args, **kwargs):
            if url is None: return None
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', str(url)):
                u = urlsplit(str(url))
                if u.scheme not in ('http','https') or u.hostname not in ('www.xbrl.org','www.w3.org') or u.username or u.password:
                    return None
                if '..' in unquote(u.path).split('/') or '\\' in unquote(u.path): return None
            # Preserve Arelle's built-in-cache fallback. workOffline forbids downloads.
            resolved = original(url, *args, **kwargs)
            if resolved is None: return None
            candidate = Path(resolved).resolve()
            if not (candidate.is_relative_to(root.resolve()) or candidate.is_relative_to(builtin)): return None
            return str(candidate) if candidate.is_file() else None
        controller.webCache.getfilename = local_only
        try:
            model = controller.modelManager.load(str(path))
            need(model is not None and model.modelDocument is not None, 'ARELLE_LOAD')
            need(len(model.facts) <= 50000, 'FACT_BOUND')
            for f in model.facts:
                if f.qname is None: continue
                # isNumeric depends on a loaded concept; skipDTS deliberately has none.
                numeric = f.localName == 'nonFraction'
                if f.localName not in ('nonFraction','nonNumeric'): continue
                ns, tag = f.qname.namespaceURI, f.qname.localName
                if not IFRS.fullmatch(ns):
                    if numeric and len(issues)<32: issues.append(dict(tag=tag[:128], reason='UNREVIEWED_EXTENSION'))
                    continue
                if tag not in TAGS and tag not in ('NameOfReportingEntityOrOtherMeansOfIdentification',
                        'DescriptionOfNatureOfFinancialStatements', 'DateOfEndOfReportingPeriod2013'): continue
                c = f.context
                if not group_context(c): continue
                try:
                    value = f.value
                    if f.isNil: continue
                    start = c.startDatetime.date().isoformat() if c.isStartEndPeriod else None
                    end = (c.endDatetime.date()-timedelta(days=1)).isoformat() if c.isStartEndPeriod else None
                    measures = f.unit.measures if numeric and f.unit is not None else None
                    currency = None
                    if measures and len(measures[0]) == 1 and not measures[1]:
                        q = measures[0][0]
                        if q.namespaceURI == 'http://www.xbrl.org/2003/iso4217': currency = q.localName
                    dimensions = {expanded(d): expanded(v.memberQname) for d,v in c.qnameDims.items()}
                    record = dict(taxonomy=ns, tag=tag, value=decimal(value) if numeric else str(value).strip(),
                        numeric=numeric, currency=currency, start=start, end=end,
                        entity_scheme=c.entityIdentifier[0], entity=c.entityIdentifier[1], context_id=c.id,
                        dimensions=dimensions, member=member, member_sha256=sha,
                        position='ix:'+member+'#element='+str(f.objectIndex), fact_id=f.id,
                        original_value=f.rawValue if numeric else str(value).strip(),
                        scale=f.get('scale', '0'), sign=f.get('sign', ''), decimals=f.get('decimals'),
                        transform=expanded(f.format) if f.format is not None else None)
                    if numeric:
                        need(re.fullmatch(r'-?[0-9]{1,2}', record['scale']) and abs(int(record['scale']))<=18
                             and record['sign'] in ('','-') and isinstance(record['decimals'],str)
                             and re.fullmatch(r'INF|-?[0-9]{1,2}',record['decimals']), 'NUMBER')
                    need(len(record['original_value']) <= 2048 and len(record['position']) <= 400, 'FACT_BOUND')
                    out.append(record)
                except (ValueError, ArithmeticError, TypeError, FunctionArgType, ixtFunctionNotAvailable):
                    issues.append(dict(tag=tag, reason='INVALID_TRANSFORM_OR_NUMBER'))
            # Raw Arelle messages can contain source text: never expose them.
            # Arelle 2.47.3 emits this code for undefined concepts in skipDTS.
            # Missing ix:references targets and all other structural errors remain fatal.
            isolated_code = 'ix11.10.1.1:transformValueError'
            isolated_logs = [r for r in controller.logHandler.logRecordBuffer
                             if getattr(r, 'messageCode', None) == isolated_code]
            need(len(isolated_logs) == model.errors.count(isolated_code), 'ARELLE_STRUCTURE')
            excluded = set()
            for log in isolated_logs:
                refs = getattr(log, 'refs', [])
                need(len(refs) == 1 and 'objectId' in refs[0], 'ARELLE_STRUCTURE')
                fact = model.modelObject(refs[0]['objectId'])
                need(fact is not None and fact in model.facts and fact.localName == 'nonFraction'
                     and getattr(fact, 'xValid', None) == INVALID, 'ARELLE_STRUCTURE')
                position = 'ix:'+member+'#element='+str(fact.objectIndex)
                excluded.add(position)
                issues.append(dict(tag=fact.qname.localName, position=position,
                                   reason='INVALID_NUMERIC_TRANSFORM', arelle_code=isolated_code))
            out = [r for r in out if r['position'] not in excluded]
            # Only fully bound invalid numeric facts may be isolated. No schema,
            # document, unknown transformation or other unknown code is waived.
            need(not (set(model.errors)-{'ix11.12.1.2:missingReferences', isolated_code}), 'ARELLE_STRUCTURE')
        finally:
            controller.modelManager.close(); controller.close(saveConfig=False)
    return out, issues


def qualify(rows, issues, metadata, identity, profile):
    need(identity['isin'] == profile['isin'] and identity['name'] in profile['names'], 'IDENTITY')
    norm = lambda s: re.sub('[^A-Z0-9]', '', s.upper())
    own = [r for r in rows if r['entity'] == profile['lei'] and r['entity_scheme'] in
           ('http://standards.iso.org/iso/17442', 'https://standards.iso.org/iso/17442')]
    need(bool(own), 'LEI')
    names = [r for r in own if r['tag']=='NameOfReportingEntityOrOtherMeansOfIdentification']
    need(names and all(norm(r['value']) in {norm(n) for n in profile['names']} for r in names), 'ENTITY_NAME')
    nature = [r for r in own if r['tag']=='DescriptionOfNatureOfFinancialStatements'
              and re.search(r'\bconsolidated\b', r['value'], re.I)
              and not re.search(r'\b(non.consolidated|unconsolidated|separate)\b', r['value'], re.I)]
    need(nature, 'CONSOLIDATED_SCOPE')
    ends = [r for r in own if r['tag']=='DateOfEndOfReportingPeriod2013']
    need(ends and {r['value'] for r in ends} == {profile['report_end']}, 'REPORT_END')
    scope_members = {r['member'] for r in nature} & {r['member'] for r in names} & {r['member'] for r in ends}
    need(scope_members, 'CONSOLIDATED_SCOPE')
    years = profile['years']
    need(len(years)==2 and years[1]==years[0]+1 and int(profile['report_end'][:4])==years[1], 'YEARS')
    candidates = [r for r in own if r['member'] in scope_members and r['tag'] in TAGS and r['numeric'] and r['start'] and r['end']
                  and (date.fromisoformat(r['end'])-date.fromisoformat(r['start'])).days+1 in (364,365,366,371)]
    periods = {}
    for year in years:
        pairs = {(r['start'], r['end']) for r in candidates if r['end'][:4] == str(year)}
        need(len(pairs)==1, 'ANNUAL_PERIOD_AMBIGUOUS')
        start,end = pairs.pop(); periods[str(year)] = dict(start=start, end=end)
    need(periods[str(years[1])]['end']==profile['report_end'] and
         date.fromisoformat(periods[str(years[0])]['end'])+timedelta(days=1)==date.fromisoformat(periods[str(years[1])]['start']), 'PERIOD_CONTINUITY')
    observations=[]; facts=[]; gaps=[]
    for year in reversed(years):
        period=periods[str(year)]
        for tag, metric in TAGS.items():
            found=[r for r in candidates if r['tag']==tag and (r['start'],r['end'])==(period['start'],period['end'])]
            reason = None
            if not found: reason='NO_QUALIFIED_STANDARD_DURATION_FACT'
            elif any(r['currency']!=profile['expected_currency'] for r in found): reason='UNIT_CONFLICT'
            elif len({Decimal(r['value']) for r in found})!=1: reason='CONFLICTING_DUPLICATE_FACTS'
            elif len(found)>32: reason='DUPLICATE_BOUND'
            if reason:
                gaps.append(dict(metric=metric, fiscal_year=str(year), reason=reason)); continue
            found.sort(key=lambda r:r['position']); r=found[0]; i=len(facts)
            observations.append(dict(metric_key=metric,value_decimal=r['value'],unit_key=r['currency'],unit_version='1',
                period_type='fy',fiscal_year=str(year),fiscal_quarter=None,period_start=r['start'],period_end=r['end'],
                estimate_horizon=None,as_of_at=None,reported_at=None,observed_at=metadata['observed_at'],
                field_path=f'evidence:facts/{i};source='+r['position'],value_type='decimal',dimension_key='monetary',value_text=None,value_date=None))
            facts.append(dict(metric_key=metric,fiscal_year=str(year),period_start=r['start'],period_end=r['end'],
                normalized_value=r['value'],normalized_unit=r['currency'],original_unit=r['currency'],
                source_url=metadata['url'],validation_status='qualified',selected=r,occurrences=found))
    need(observations, 'NO_QUALIFIED_FACTS')
    keys=sorted({r['metric_key'] for r in observations}); currency=profile['expected_currency']
    plan=dict(fiscal_calendar='reported_fy',reported_periods=periods,source=profile['source'],parser_key=PARSER,
        parser_version='1',parse_status='parsed',metadata=metadata,
        units=[dict(unit_key=currency,unit_version='1',display_name=profile['currency_name'],dimension_key='monetary',
            monetary_currency_code=currency,scale_numerator='1',scale_denominator='1',status='frozen')],
        metrics=[dict(metric_key=k,display_name=DEFS[k][0],category='cashflow' if k=='operating_cashflow' else 'income',
            value_type='decimal',value_semantics=DEFS[k][1],dimension_key='monetary',status='active') for k in keys],
        observations=observations,unqualified_metrics=gaps)
    doc=dict(format='mosa2-fundamental-evidence-v1',kind='derived_evidence',evidence_type='esef_inline',
        source_response=dict(metadata,retained=False),issuer=identity,identity_mapping=profile,
        source_classification='official_issuer_esef',parser=dict(key=PARSER,version='1'),
        arelle_version=VERSION,qualification_scope='allowlisted_IFRS_facts_not_full_DTS_validation',
        identity_evidence=names,consolidation_evidence=nature,report_end_evidence=ends,
        reported_periods=periods,facts=facts,gaps=gaps,structural_issues=issues[:32])
    compact=encode(doc); need(len(compact)<=131072, 'EVIDENCE_BOUND')
    plan['evidence_json']=compact.decode('utf-8')
    plan['stored_evidence']=dict(metadata,kind='derived_evidence',content_type='application/json',bytes=len(compact),sha256=hashlib.sha256(compact).hexdigest())
    return plan


def parse(raw, metadata, identity, profile):
    need(metadata['url']==profile['url'] and metadata['http_status']==200
         and metadata['sha256']==hashlib.sha256(raw).hexdigest() and metadata['bytes']==len(raw), 'RESPONSE_BINDING')
    with package(raw) as (root, reports): rows, issues = records(root, reports)
    return qualify(rows, issues, metadata, identity, profile)
