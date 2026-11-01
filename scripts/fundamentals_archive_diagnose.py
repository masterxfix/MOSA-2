"""One read-only SSH diagnosis. No DB credentials, tunnel, writes or provider HTTP."""
import json
import logging
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from scripts import collector_actions as access
from scripts.fundamentals import zeiss
from scripts.fundamentals.archived_zeiss import load

AUTHORIZATION='MOSA2-ZEISS-ARCHIVE-DIAGNOSE-V2-20261101:'
ERRORS={'REPORT_IDENTITY_OR_UNITS','NESTED_TABLE','AMBIGUOUS_RESULTS_TABLE','FISCAL_COLUMN_ORDER',
        'DUPLICATE_METRIC','RESULT_COLUMNS','RESULT_VALUE_OR_UNIT','EPS_BASIC_QUALIFICATION','EBITDA_QUALIFICATION','HTTP_RESPONSE'}

def guard(env,authorization=AUTHORIZATION):
    for k,v in dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='1').items():
        if env.get(k)!=v:raise ValueError('RUN_GUARD')
    sha=env.get('GITHUB_SHA','')
    if not re.fullmatch('[0-9a-f]{40}',sha) or env.get('EXPECTED_COMMIT')!=sha or env.get('AUTHORIZATION')!=authorization+sha:raise ValueError('RUN_GUARD')

def diagnose(raw,metadata):
    error='NONE'
    try:
        if metadata['http_status']!=200 or not metadata['content_type'].lower().startswith('text/html'):raise ValueError('HTTP_RESPONSE')
        zeiss.parse(raw,metadata['observed_at'])
    except ValueError as exc:error=str(exc) if str(exc) in ERRORS else 'UNCLASSIFIED_ADAPTER_ERROR'
    except Exception:error='UNCLASSIFIED_ADAPTER_ERROR'
    result=dict(first_error=error,http_status=metadata['http_status'],content_type_html=metadata['content_type'].lower().startswith('text/html'))
    if error in ('HTTP_RESPONSE','UNCLASSIFIED_ADAPTER_ERROR'):return result
    text=zeiss.clean(zeiss.normalized_text(raw))
    terms=['Carl Zeiss Meditec','2024/25','2023/24','Zusammenfassung wesentlicher Größen der Konzern-Gewinn- und Verlustrechnung','Angaben in Mio. €']
    compact=lambda s:re.sub(r'\s+','',zeiss.clean(s))
    result['identity_checks']=[dict(term=i,exact=t in text,without_whitespace=compact(t) in compact(text)) for i,t in enumerate(terms)]
    tables=zeiss.Tables()
    try:tables.feed(raw.decode('utf-8'))
    except ValueError:return result
    result['matching_tables']=sum(set(zeiss.ROWS).issubset({r[0] for r in t if r}) for t in tables.tables)
    result['expected_headings_present']=all(x['exact'] for x in result['identity_checks'])
    result['tables']=[]
    for ti,table in enumerate(tables.tables[:12]):
        rows=[];headers=[]
        for ri,row in enumerate(table[:80]):
            if any(y in c for c in row for y in ('2024/25','2023/24')):
                headers.append([c if c in ('2024/25','2023/24') else 'EMPTY' if not c else 'OTHER' for c in row[:16]])
            for ci,cell in enumerate(row[:16]):
                keys=[key for label,key in zeiss.ROWS.items() if compact(label)==compact(cell)]
                if keys:
                    types=[]
                    for c in row[:16]:
                        types.append('EMPTY' if not c else 'LABEL' if c==cell else 'NUMBER' if re.fullmatch(zeiss.NUMBER,c) else 'PERCENT' if re.fullmatch(zeiss.NUMBER+r'\s*%',c) else 'EURO' if re.fullmatch(zeiss.NUMBER+r'\s*€',c) else 'OTHER')
                    rows.append(dict(row=ri,label_cell=ci,metric=keys[0],exact=cell in zeiss.ROWS,cells=types))
        if rows:result['tables'].append(dict(table=ti,headers=headers[:4],rows=rows[:24]))
    matching=[t for t in result['tables'] if len({r['metric'] for r in t['rows']})==len(zeiss.ROWS)]
    result['recognized_metric_keys']=sorted({r['metric'] for t in result['tables'] for r in t['rows']})
    result['column_structure_valid']=len(matching)==1 and all(len([c for c in r['cells'] if c!='EMPTY'])==4 for r in matching[0]['rows'])
    result['number_unit_formats_valid']=bool(matching) and all(
        [c for c in r['cells'] if c!='EMPTY'][1:3]==[{'monetary':'NUMBER','monetary_per_share':'EURO','ratio':'PERCENT'}[zeiss.DEFINITIONS[r['metric']][2]]]*2
        for t in matching for r in t['rows'])
    result['first_validation_deviation']=error
    return result

def execute(env):
    report=dict(ok=False,provider_requests=0,database_access=False,archive_writes=False)
    phase='GUARDS'
    try:
        guard(env)
        phase='CONFIGURATION'
        config=access.profile.configuration(env)
        phase='SSH_CONNECT'
        import paramiko
        logging.getLogger('paramiko').disabled=True
        with access.ssh_client(config,{},paramiko) as transport:
            phase='SSH_REMOTE_DIAGNOSIS'
            report=load(transport)
    except Exception as exc:
        allowed={'RUN_GUARD','SSH_OUTPUT_LIMIT','SSH_STDERR_LIMIT','SSH_COMMAND_TIMEOUT','SSH_SESSION_CHANNEL_REJECTED',
            'SSH_EXEC_REQUEST_REJECTED','REMOTE_STDERR','RESULT_BOUND','REMOTE_INVALID_JSON','REMOTE_RESULT_INVALID'}
        fallback={'GUARDS':'GUARD_FAILED','CONFIGURATION':'CONFIGURATION_INVALID','SSH_CONNECT':'SSH_CONNECTION_FAILED',
            'SSH_REMOTE_DIAGNOSIS':'REMOTE_TRANSPORT_FAILED'}
        report.update(phase=phase,error=str(exc) if str(exc) in allowed else fallback[phase])
    return report

if __name__=='__main__':
    result=execute(os.environ);print(access.public_text(result,os.environ));sys.exit(0 if result['ok'] else 1)
