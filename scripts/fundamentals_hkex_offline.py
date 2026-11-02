"""Offline HKEX qualification driver; reads already downloaded PDFs only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.fundamentals import hkex


def qualify(path, profile_key, observed_at):
    raw=Path(path).read_bytes()
    profile=hkex.profile_for(profile_key)
    metadata=dict(url=profile['url'],observed_at=observed_at,http_status=200,content_type='application/pdf',
                  bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    plan=hkex.parse(raw,metadata,profile)
    evidence=plan['stored_evidence']['sha256']
    plan['archive']=dict(storage_key=f'/private/mosa2/hkex/{profile_key}/evidence.json',
                         sha256=evidence,bytes=plan['stored_evidence']['bytes'],durable=True)
    return plan


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--byd-pdf',required=True)
    parser.add_argument('--ubtech-pdf',required=True)
    parser.add_argument('--observed-at',default=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f'))
    parser.add_argument('--php-check',action='store_true')
    parser.add_argument('--summary-only',action='store_true')
    args=parser.parse_args(argv)
    plans=[qualify(args.byd_pdf,'byd-company-fy2025',args.observed_at),
           qualify(args.ubtech_pdf,'ubtech-robotics-fy2025',args.observed_at)]
    if args.php_check:
        result=subprocess.run([r'C:\php\php.exe','tests/fundamentals_hkex.php'],input=json.dumps(plans,ensure_ascii=True),
                              text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1],check=False)
        if result.stderr or result.returncode:
            raise RuntimeError('PHP_OFFLINE_PIPELINE')
        php=json.loads(result.stdout)
    else:
        php=None
    if args.summary_only:
        summary=[]
        for plan in plans:
            doc=json.loads(plan['evidence_json'])
            summary.append(dict(profile=plan['hkex_profile']['profile_key'],isin=plan['identity']['isin'],observations=len(plan['observations']),
                values=[dict(metric=f['metric_key'],fy=f['fiscal_year'],value=f['normalized_value'],unit=f['original_unit'],page=f['page'],column=f['column']) for f in doc['facts']],
                source_response_sha256=plan['metadata']['sha256'],evidence_sha256=plan['stored_evidence']['sha256'],evidence_bytes=plan['stored_evidence']['bytes'],
                gaps=plan['unqualified_metrics']))
        print(json.dumps(dict(ok=True,provider_requests=0,db_writes=0,actions=0,summary=summary,php=php),ensure_ascii=True,separators=(',',':')))
    else:
        print(json.dumps(dict(ok=True,provider_requests=0,db_writes=0,actions=0,plans=plans,php=php),ensure_ascii=True,separators=(',',':')))


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps(dict(ok=False,provider_requests=0,db_writes=0,actions=0,error=str(exc)),ensure_ascii=True))
        raise
