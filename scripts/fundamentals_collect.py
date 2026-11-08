"""Manual sequential reports; shared transport, archive, SQL transaction and readback."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals.reports import APPROVED_REPORTS, APPROVED_SINGLE_REPORTS, selection

def collect(env, keys, execute=shared.execute):
    reports=[dict(r,authorization='MOSA2-REPORTS-'+','.join(keys)+':',reusable_manual=True) for r in selection(keys)]
    if tuple(keys) not in (APPROVED_REPORTS, APPROVED_SINGLE_REPORTS):raise ValueError('REPORT_AUTHORIZATION')
    # All authorizations are checked before the first connection or GET.
    for report in reports:shared.guard(env,report)
    results=[]
    for key,report in zip(keys,reports):
        result=execute(env,report)
        results.append(dict(report=key,**result))
        if not result.get('ok'):break  # Unknown outcome never retries or starts the next report.
    return dict(ok=len(results)==len(reports) and all(r['ok'] for r in results),
                provider_requests=sum(r['provider_requests'] for r in results),reports=results)

if __name__=='__main__':
    try:result=collect(os.environ,os.environ.get('REPORT_KEYS','').split(','))
    except Exception:result=dict(ok=False,stage='REPORT_GUARDS',provider_requests=0)
    public=shared.access.public_text(result,os.environ)
    print(public)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as out:
            out.write('Manual qualified reports\n\n```json\n'+public+'\n```\n')
    sys.exit(0 if json.loads(public).get('ok') else 1)
