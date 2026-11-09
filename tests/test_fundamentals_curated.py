import copy
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from scripts import fundamentals_curated as runner
from scripts.fundamentals.curated import load, METHOD
from test_fundamentals_pilot import plan as annual, OBSERVED, PilotTests
from test_fundamentals_generic import zeiss_plan
archive_test=PilotTests.test_private_archive_exclusive_durable_readback_and_tamper_rejection
del PilotTests

MANIFEST=runner.shared.ROOT/'scripts/fundamentals/manifests/droneshield-fy2025-v1.json'
IDENTITY=dict(isin='AU000000DRO2',name='DroneShield')


def fixture():
    m=json.loads(MANIFEST.read_bytes())
    for i,f in enumerate(m['facts']):f['value']=str(-10-i)+'.1' if i%2 else str(20+i)+'.2'
    return m


def plan(manifest=None):
    raw=json.dumps(manifest or fixture(),ensure_ascii=False,indent=2).encode('utf-8')
    p,body,stored=load(raw,OBSERVED,(manifest or fixture())['issuer'])
    p['archive']=dict(storage_key='/private/synthetic/evidence.json',sha256=stored['sha256'],bytes=len(body),durable=True)
    return p


class CuratedTests(unittest.TestCase):
    def test_snapshot_and_period_packets_with_independent_delta_and_history_only_projection(self):
        profiles=[runner.PROFILES[k] for k in ('nel-q2-2026-balances-orders-v1','nel-registered-shares-2025-v1')]
        plans=[]
        for profile in profiles:
            raw=(runner.shared.ROOT/profile['manifest']).read_bytes()
            p,body,stored=load(raw,'2026-11-09 15:03:00.000000',profile['identity'])
            p['archive']=dict(storage_key='/private/synthetic/evidence.json',sha256=stored['sha256'],bytes=len(body),durable=True)
            plans.append(p)
        self.assertEqual([(r['metric_key'],r['value_decimal'],r['period_type']) for r in plans[0]['observations']],[
            ('cash_balance','1328048','snapshot'),('total_equity','3601586','snapshot'),('order_intake','230','fq'),
            ('order_backlog','1213','snapshot'),('order_backlog_risk_amount','296','snapshot')])
        self.assertFalse(plans[1]['publish_current'])
        self.assertEqual(plans[1]['observations'][0]['as_of_at'],'2025-03-25 00:00:00.000000')
        result=subprocess.run(['php','tests/fundamentals_snapshot_readback.php'],input=json.dumps([annual(),zeiss_plan(),*plans]),text=True,capture_output=True,cwd=runner.shared.ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_authorized_manifest_exact_rounded_values_and_provenance(self):
        raw=MANIFEST.read_bytes();p,body,stored=load(raw,OBSERVED,IDENTITY)
        self.assertEqual([(f['value_decimal']) for f in p['observations']],
            ['216.5','57.5','201.6','56.6','4.5','-8.6','36.5','-4.0','33.3','-2.1','3.5','-1.3','15.9','-62.2'])
        self.assertEqual(len(p['metrics']),7);self.assertEqual(len(p['observations']),14)
        self.assertEqual({r['period_end'] for r in p['observations']},{'2025-12-31','2024-12-31'})
        self.assertEqual(p['units'][0]['monetary_currency_code'],'AUD')
        doc=json.loads(body);self.assertIsNone(doc['research']['researched_at']);self.assertFalse(doc['http_request_performed'])
        self.assertIsNone(p['metadata']['http_status']);self.assertNotIn('request_started_at',p['metadata'])
        self.assertNotIn('source_response',doc);self.assertEqual(doc['input_manifest']['payload_kind'],'curated_manifest')
        self.assertEqual(hashlib.sha256(doc['manifest_json'].encode()).hexdigest(),p['metadata']['sha256'])
        self.assertEqual(hashlib.sha256(body).hexdigest(),stored['sha256'])
        self.assertTrue(all(f['rounded'] and f['decimal_places']==1 for f in doc['facts']))

    def test_generic_second_issuer_and_explicit_noncalendar_periods(self):
        m=fixture();m['issuer']=dict(isin='DE000A0JBPG2',name='Synthetic Issuer');m['manifest_id']='synthetic-v1'
        m['primary_url']='https://example.invalid/report';m['source']['base_url']='https://example.invalid/'
        m['fiscal_year_start_month']=7
        for key,p in m['periods'].items():
            y=int(p['fiscal_year']);p['period_start']=f'{y-1}-07-01';p['period_end']=f'{y}-06-30'
        p=plan(m);self.assertEqual(p['fiscal_year_start_month'],7)
        self.assertEqual(p['observations'][0]['period_start'],'2024-07-01')

    def test_missing_conflicting_identity_source_precision_and_duplicates(self):
        variants=[]
        for path,value in [(('input_method',),'http_get'),(('source','source_type'),'issuer_release'),
            (('primary_url',),'https://other.invalid/report'),(('research','review_status'),'unreviewed'),
            (('research','researched_at'),'2099-01-01 00:00:00.000000')]:
            m=fixture();target=m
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value;variants.append(m)
        for field,value in [('value',1.2),('value','NaN'),('value','12.34'),('rounded',False),('unit_key','EUR_MILLION'),('original_unit','USD'),('section','')]:
            m=fixture();m['facts'][0][field]=value;variants.append(m)
        m=fixture();m['facts'].append(dict(m['facts'][0],value='999.9'));variants.append(m)
        m=fixture();del m['facts'][0]['value'];variants.append(m)
        for m in variants:
            with self.subTest(manifest=m['manifest_id']),self.assertRaises((ValueError,KeyError,TypeError)):load(json.dumps(m).encode(),OBSERVED,IDENTITY)
        with self.assertRaisesRegex(ValueError,'CURATED_IDENTITY'):load(MANIFEST.read_bytes(),OBSERVED,dict(isin='DE000A0JBPG2',name='Other'))
        with self.assertRaisesRegex(ValueError,'CURATED_DUPLICATE_KEY'):load(b'{"a":1,"a":2}',OBSERVED,IDENTITY)

    def test_shared_transaction_catalog_preservation_hashes_rollback_and_readback(self):
        result=subprocess.run(['php','tests/fundamentals_curated.php'],input=json.dumps([annual(),zeiss_plan(),plan()]),text=True,capture_output=True,cwd=runner.shared.ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(result.stderr,'')
        self.assertTrue(json.loads(result.stdout)['ok'])

    def test_private_curated_evidence_protection_and_hash(self):
        archive_test(self,derived=True,curated=True)

    def test_runner_zero_provider_calls_commit_guard_and_single_application(self):
        env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1',
            GITHUB_SHA='a'*40,EXPECTED_COMMIT='a'*40,AUTHORIZATION='MOSA2-CURATED-droneshield-fy2025-v1:'+'a'*40,MANIFEST_KEY='droneshield-fy2025-v1')
        calls=[]
        def archive(transport,action,env,identity=None,metadata=None,payload=None,selected=None):
            calls.append(action)
            if action=='reserve':return dict(identity={})
            if payload is not None:self.assertEqual(json.loads(payload)['input_method'],METHOD)
            return dict(storage_key='/private/evidence.json',sha256=metadata['sha256'],bytes=metadata['bytes'],durable=True)
        def database(env,port,action,**kwargs):
            calls.append(action)
            if action=='inspect':return dict(asset_id='103',baseline={},protected={}),0
            self.assertIsNone(kwargs['plan']['metadata']['http_status']);return dict(ok=True,readback='PASS'),0
        with patch.object(runner.shared,'no_other_runs'),patch.object(runner.shared.access,'configuration'), \
            patch.object(runner.shared.access,'ssh_client',return_value=nullcontext(object())),patch.object(runner.shared.access,'tunnel',return_value=nullcontext(3306)), \
            patch.object(runner.shared,'archive',side_effect=archive),patch.object(runner.shared,'database',side_effect=database), \
            patch.object(runner.shared.ReadOnlyHttpTransport,'fetch',side_effect=AssertionError('provider prohibited')) as http, \
            patch('urllib.request.urlopen',side_effect=AssertionError('provider prohibited')):
            result=runner.execute(env);self.assertTrue(result['ok'],result);http.assert_not_called()
            self.assertEqual(result['provider_requests'],0);self.assertEqual(calls,['inspect','reserve','archive','verify','apply','verify'])
            calls.clear();result=runner.execute(env|dict(GITHUB_RUN_ATTEMPT='2'))
            self.assertFalse(result['ok']);self.assertEqual(calls,[])
            with patch.object(runner.shared,'database',side_effect=RuntimeError('COMMIT')):
                result=runner.execute(env);self.assertFalse(result['ok']);self.assertEqual(result['provider_requests'],0)
