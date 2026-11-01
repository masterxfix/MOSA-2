"""Manual manifest import. Shared archive/SQL/readback, deliberately no provider transport."""
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import fundamentals_pilot_once as shared
from scripts.fundamentals.curated import load

PROFILES={
    'droneshield-fy2025-v1':dict(manifest='scripts/fundamentals/manifests/droneshield-fy2025-v1.json',
        execution='fundamentals-curated-droneshield-fy2025-20261101-01',
        authorization='MOSA2-CURATED-droneshield-fy2025-v1:',reusable_manual=True,
        identity=dict(isin='AU000000DRO2',name='DroneShield'),
        preserve_assets=[dict(isin='DE000A0JBPG2',name='PNE AG',observations=11,current=6),
                         dict(isin='DE0005313704',name='Carl Zeiss Meditec',observations=20,current=10)])
}


def execute(env):
    report=dict(ok=False,provider_requests=0,pdf_downloads=0,full_responses_archived=0,observations=0,current=0)
    stage='GUARDS'
    try:
        selected=PROFILES[env['MANIFEST_KEY']]
        shared.guard(env,selected)
        stage='MANIFEST_VALIDATION'
        raw=(shared.ROOT/selected['manifest']).read_bytes()
        imported_at=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')
        plan,compact,stored=load(raw,imported_at,selected['identity'])
        shared.no_other_runs(env);config=shared.access.configuration(env)
        import paramiko
        logging.getLogger('paramiko').disabled=True
        stage='SSH'
        with shared.access.ssh_client(config,{},paramiko) as transport:
            with shared.access.tunnel(transport,{}) as port:
                stage='DB_PREFLIGHT'
                before,elapsed=shared.database(env,port,'inspect',selected=selected)
                report['preflight_runner_ms']=elapsed
                stage='PRIVATE_RESERVATION'
                reserved=shared.archive(transport,'reserve',env,selected=selected)
                stage='EVIDENCE_ARCHIVE'
                shared.archive(transport,'archive',env,reserved['identity'],stored,compact,selected=selected)
                verified=shared.archive(transport,'verify',env,reserved['identity'],stored,selected=selected)
                plan['archive']=verified
                report.update(evidence_sha256=stored['sha256'],evidence_bytes=stored['bytes'],evidence_archive='PASS',
                    input_method='manually_reviewed_public_facts',research_time='UNKNOWN_PRIOR_TO_ASSIGNMENT',qualified_metrics=len(plan['metrics']))
                stage='DB_APPLY_AND_READBACK'
                result,elapsed=shared.database(env,port,'apply',selected=selected,baseline=before['baseline'],protected=before['protected'],asset_id=before['asset_id'],plan=plan)
                stage='FINAL_EVIDENCE_READBACK'
                shared.archive(transport,'verify',env,reserved['identity'],stored,selected=selected)
                report.update(result,apply_runner_ms=elapsed,commit=env['GITHUB_SHA'],imported_at=imported_at,
                              http_request_performed=False,http_status=None,source_classification='independent_third_party_report_reproduction')
        report['stage']='SUCCESS'
    except Exception as error:
        report.update(stage=stage,outcome='UNKNOWN_NO_RETRY' if stage in ('DB_APPLY_AND_READBACK','FINAL_EVIDENCE_READBACK') else 'STOP_NO_RETRY')
        allowed={'CURATED_BOUND','CURATED_DUPLICATE_KEY','CURATED_FORMAT','CURATED_ID','CURATED_IDENTITY','CURATED_REVIEW','CURATED_RESEARCH_TIME',
            'CURATED_SOURCE','CURATED_CATALOG','CURATED_PERIOD','CURATED_FACT_BINDING','CURATED_DUPLICATE_FACT','CURATED_DECIMAL_STRING','CURATED_PRECISION',
            'CURATED_LOCATOR','CURATED_UNIT','CURATED_UNUSED_CATALOG','RUN_GUARD','COMMIT_AUTHORIZATION'}
        if str(error) in allowed:report['error_code']=str(error)
        if type(error) is RuntimeError and str(error) in {'INPUT','IDENTITY','SCHEMA6','PLAN','TRANSACTION','COMMIT','INDEPENDENT_READBACK'}:report['db_stage']=str(error)
    return report


if __name__=='__main__':
    result=execute(os.environ);public=shared.access.public_text(result,os.environ);print(public)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as out:out.write('Curated facts import (zero provider requests)\n\n```json\n'+public+'\n```\n')
    sys.exit(0 if result['ok'] else 1)
