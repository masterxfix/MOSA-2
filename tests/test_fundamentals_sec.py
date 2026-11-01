import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch, Mock
from contextlib import nullcontext
from scripts.fundamentals import sec_xbrl as sec
from scripts import fundamentals_sec_once as runner
from scripts.fundamentals.analysis import build
from scripts.fundamentals.assessment import prepare

STAMP='2026-11-01 17:00:00.000000'


def fixture(profile=runner.PROFILES[0]):
    periods=(('2024-01-29','2025-01-26'),('2025-01-27','2026-01-25')) if profile['years']==(2025,2026) else (('2024-01-01','2024-12-31'),('2025-01-01','2025-12-31'))
    facts={}
    for tag in sec.TAGS:
        if tag=='ProfitLoss':continue
        rows=[]
        for i,(year,(start,end)) in enumerate(zip(profile['years'],periods)):
            value=(100+i*20) if 'Revenue' in tag else (-30+i*10)
            rows.append(dict(start=start,end=end,val=value,accn='0000123456-26-000001',fy=year,fp='FY',form='10-K',filed='2026-03-01'))
        facts[tag]=dict(label=tag,description='Synthetic definition',units={'USD':rows})
    return dict(cik=int(profile['cik']),entityName=profile['sec_names'][0],facts={'us-gaap':facts})


def plan(data=None,profile=runner.PROFILES[0]):
    data=fixture(profile) if data is None else data
    raw=json.dumps(data).encode();meta=dict(url=sec.url(profile['cik']),request_started_at=STAMP,observed_at=STAMP,
        http_status=200,content_type='application/json',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),execution=profile['execution'],commit='a'*40)
    mapping={k:profile[k] for k in ('cik','isin','sec_names','reference')};mapping['verification']='reviewed_cik_isin'
    p=sec.parse(raw,meta,dict(isin=profile['isin'],name=profile['name']),mapping,profile['years'])
    p['archive']=dict(storage_key='/private/synthetic/'+profile['cik']+'/evidence.json',sha256=p['stored_evidence']['sha256'],bytes=p['stored_evidence']['bytes'],durable=True)
    return p


def snapshot(p):
    rows=[];current={}
    for i,r in enumerate(p['observations']):
        rows.append(dict(r,id=str(i+1),source_id='1',fetch_id='1',parser_key=p['parser_key'],parse_status='parsed',
            evidence_sha256=p['stored_evidence']['sha256'],monetary_currency_code='USD',scale_numerator='1',scale_denominator='1'))
        current.setdefault(r['metric_key']+':fy',[dict(observation_id=str(i+1))])
    return build(dict(id='1',name='Synthetic',identifiers=[dict(normalized_value='US67066G1040')],facts=rows,current=current,market_sources=[]),[dict(id='1',source_type='regulator_xbrl')])


class SecTests(unittest.TestCase):
    def test_two_issuers_same_parser_usd_and_distinct_accounting(self):
        for profile in runner.PROFILES:
            p=plan(profile=profile)
            self.assertEqual(len(p['observations']),8)
            self.assertEqual({r['unit_key'] for r in p['observations']},{'USD'})
            self.assertNotIn('ebit',{r['metric_key'] for r in p['observations']})
            self.assertIn('profit_attributable_to_owners',{r['metric_key'] for r in p['observations']})
            self.assertEqual({r['fiscal_year'] for r in p['observations']},{str(y) for y in profile['years']})
            s=snapshot(p);prepare(s)
            self.assertEqual(sum(c['kind']=='absolute_change' for c in s['calculations']),4)
            self.assertEqual(sum(c['kind']=='growth_percent' for c in s['calculations']),1)
            self.assertTrue(any(w['code']=='NONPOSITIVE_BASE_NO_GROWTH_PERCENT' for w in s['warnings']))
    def test_identity_and_response_hash(self):
        for key,value in [('cik',999),('entityName','Unrelated issuer')]:
            data=fixture();data[key]=value
            with self.assertRaisesRegex(ValueError,'SEC_IDENTITY'):plan(data)
        p=plan();meta=p['metadata'];meta['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'SEC_RESPONSE_BINDING'):
            sec.parse(json.dumps(fixture()).encode(),meta,{},runner.PROFILES[0],(2025,2026))
        mapping=dict(runner.PROFILES[0],verification='reviewed_cik_isin')
        p=plan()
        with self.assertRaisesRegex(ValueError,'SEC_IDENTITY'):
            sec.parse(json.dumps(fixture()).encode(),p['metadata'],dict(isin='US76655K1034'),mapping,(2025,2026))
    def test_53_week_year_and_noncalendar_labels(self):
        data=fixture()
        for concept in data['facts']['us-gaap'].values():
            concept['units']['USD'][0]['start']='2024-01-22'
        p=plan(data);s=snapshot(p)
        self.assertEqual(len([c for c in s['calculations'] if c['kind']=='absolute_change']),4)
        # FY label may differ from calendar end: preserve filing label.
        data=fixture()
        for concept in data['facts']['us-gaap'].values():
            for r in concept['units']['USD']:r['fy']-=1
        profile=dict(runner.PROFILES[0],years=(2024,2025))
        p=plan(data,profile);self.assertEqual({r['fiscal_year'] for r in p['observations']},{'2024','2025'});prepare(snapshot(p))
    def test_quarters_and_comparatives_cannot_label_annual_periods(self):
        data=fixture()
        for concept in data['facts']['us-gaap'].values():
            original=concept['units']['USD'][0]
            concept['units']['USD'].append(dict(original,fy=2026,frame='CY2025',val=original['val']))
            concept['units']['USD'].append(dict(original,start='2026-01-01',end='2026-03-31',fy=2026,val=999))
        p=plan(data);self.assertEqual(p['reported_periods']['2026']['end'],'2026-01-25')
        doc=json.loads(p['evidence_json']);self.assertTrue(any(r['role']=='comparative' for f in doc['facts'] for r in f['occurrences']))
        for concept in data['facts']['us-gaap'].values():
            concept['units']['USD']=[r for r in concept['units']['USD'] if r['fy']!=2025]
        with self.assertRaisesRegex(ValueError,'SEC_FY_ANCHOR_MISSING'):plan(data)
    def test_duplicates_amendments_equal_or_conflicting(self):
        for form in ['10-K','10-K/A']:
            data=fixture();rows=data['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD']
            rows.append(dict(rows[0],form=form,accn='0000123456-26-000002',filed='2026-04-01'))
            p=plan(data);self.assertEqual(len(p['observations']),8)
            rows[-1]['val']-=1
            with self.assertRaisesRegex(ValueError,'SEC_CONFLICTING_FILINGS'):plan(data)
    def test_unsupported_tags_currency_missing_not_zero(self):
        data=fixture();gaap=data['facts']['us-gaap'];gaap['Revenues']=gaap.pop('RevenueFromContractWithCustomerExcludingAssessedTax')
        gaap['OperatingIncomeLoss']['units']['EUR']=gaap['OperatingIncomeLoss']['units'].pop('USD')
        p=plan(data);keys={r['metric_key'] for r in p['observations']}
        self.assertNotIn('revenue',keys);self.assertNotIn('operating_income',keys)
        self.assertTrue(all(r['value_decimal']!='0' for r in p['observations']))
        self.assertEqual(len(p['unqualified_metrics']),6)
    def test_decimal_and_json_bounds(self):
        self.assertEqual(sec.number(12345678901234567890),'12345678901234567890')
        for x in [1.1,True,'10']:
            with self.assertRaisesRegex(ValueError,'SEC_NUMBER'):sec.number(x)
        data=fixture();data['facts']['us-gaap']['OperatingIncomeLoss']['units']['USD'][0]['val']=1.25
        self.assertIn('1.25',[r['value_decimal'] for r in plan(data)['observations']])
        p=plan();raw=b'{"cik":1,"cik":2}';meta=dict(p['metadata'],sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        with self.assertRaisesRegex(ValueError,'SEC_DUPLICATE_KEY'):
            sec.parse(raw,meta,dict(isin=runner.PROFILES[0]['isin']),dict(runner.PROFILES[0],verification='reviewed_cik_isin'),(2025,2026))
    def test_compact_evidence_and_independent_php_writer(self):
        first=plan();second=plan(profile=runner.PROFILES[1])
        self.assertNotEqual(first['metadata']['sha256'],first['stored_evidence']['sha256'])
        self.assertFalse(json.loads(first['evidence_json'])['source_response']['retained'])
        r=subprocess.run(['php','tests/fundamentals_sec.php'],input=json.dumps([first,second]),text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertEqual(r.stderr,'')
        self.assertEqual(json.loads(r.stdout)['ok'],True)
    def test_53_week_analysis_requires_continuity(self):
        p=plan();p['observations'][-1]['period_start']='2024-01-22';p['observations'][-1]['period_end']='2025-01-19'
        s=snapshot(p)
        self.assertEqual(sum(c['kind']=='absolute_change' for c in s['calculations']),3)
    def test_manual_guard_and_contact_before_any_access(self):
        env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='2',GITHUB_SHA='a'*40,EXPECTED_COMMIT='a'*40,AUTHORIZATION=runner.AUTH+'a'*40,
            GITHUB_WORKFLOW_REF='masterxfix/MOSA-2/'+runner.WORKFLOW+'@refs/heads/main',SEC_CONTACT='contact@example.org')
        with patch.object(runner.subprocess,'check_output',return_value='contact@example.org\n'):
            self.assertIn('MOSA-2',runner.guard(env))
            for k,v in [('GITHUB_RUN_NUMBER','1'),('GITHUB_RUN_ATTEMPT','2'),('SEC_CONTACT',''),('SEC_CONTACT','fake@example.org'),('EXPECTED_COMMIT','b'*40)]:
                with self.assertRaises(ValueError):runner.guard(dict(env,**{k:v}))
        with patch.object(runner,'guard',side_effect=ValueError('private secret')):
            result=runner.execute({});self.assertEqual(result['provider_requests'],0);self.assertNotIn('private',str(result))
    def test_unknown_write_stops_second_issuer_without_retry(self):
        before=dict(assets=[dict(name=p['name'],identifiers=[dict(normalized_value=p['isin'])],facts=[{}]*(6 if i==0 else 8),current={str(j):[] for j in range(3 if i==0 else 4)}) for i,p in enumerate(runner.PROFILES)])
        for a in before['assets']:
            for r in a['facts']:r['metric_key']='synthetic'
        response=Mock(payload_bytes=json.dumps(fixture()).encode(),http_status=200,content_type='application/json',collected_at=STAMP)
        http=Mock(request_started_at=STAMP,fetch=Mock(return_value=response))
        env=dict(GITHUB_SHA='a'*40)
        with patch.object(runner,'guard',return_value='MOSA synthetic'),patch.object(runner.shared,'no_other_runs'),patch.object(runner.shared.access,'configuration'),\
             patch.object(runner.shared.access,'ssh_client',return_value=nullcontext(Mock())),patch.object(runner.shared.access,'tunnel',return_value=nullcontext(1)),\
             patch.object(runner,'read_snapshot',return_value=before),patch.object(runner.shared,'archive',return_value=dict(identity={})),\
             patch.object(runner.shared,'database',side_effect=[(dict(baseline={},protected={},asset_id='1'),1),RuntimeError('COMMIT')]) as db,\
             patch.object(runner.shared,'ReadOnlyHttpTransport',return_value=http),patch.object(runner.sec,'parse',return_value=dict(plan(),observations=plan()['observations'][:2])):
            result=runner.execute(env)
        self.assertEqual(result['outcome'],'UNKNOWN_NO_RETRY');self.assertEqual(result['provider_requests'],1)
        self.assertEqual(len(result['reports']),1);self.assertEqual(db.call_count,2);self.assertEqual(http.fetch.call_count,1)

    def test_reviewed_alternative_revenue_tags_and_conflicts(self):
        for tag in ['Revenues','RevenueFromContractWithCustomerIncludingAssessedTax']:
            data=fixture();gaap=data['facts']['us-gaap']
            gaap.pop('RevenueFromContractWithCustomerExcludingAssessedTax')
            for concept in gaap.values():concept['description']='Synthetic official concept definition'
            profile=runner.PROFILES[0];raw=json.dumps(data).encode();p=plan()
            meta=dict(p['metadata'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            reviews=[dict(fiscal_year=str(y),tag=tag,scope='consolidated_total_revenue',reference=profile['reference'],start=r['start'],end=r['end'],control_usd=str(r['val'])) for y,r in zip(profile['years'],gaap[tag]['units']['USD'])]
            mapping=dict(profile,verification='reviewed_cik_isin',revenue_reviews=reviews)
            qualified=sec.parse(raw,meta,dict(isin=profile['isin'],name=profile['name']),mapping,profile['years'],revenue_only=True)
            self.assertEqual(len(qualified['observations']),2)
            self.assertEqual({r['metric_key'] for r in qualified['observations']},{'revenue'})
            qualified['archive']=dict(storage_key='/synthetic/evidence.json',sha256=qualified['stored_evidence']['sha256'],bytes=qualified['stored_evidence']['bytes'],durable=True)
            php="require 'tests/fundamentals_offline.php'; [$baseline,$p]=json_decode(stream_get_contents(STDIN),true); $db=new MemoryPDO(); Mosa2\\Fundamentals\\transaction($db,$baseline,'1',fn()=>null); $saved=$db->data['m2_fundamental_observations']; $a=Mosa2\\Fundamentals\\transaction($db,$p,'1',fn()=>null); $b=Mosa2\\Fundamentals\\transaction($db,$p,'1',fn()=>null); foreach($saved as $i=>$r)if($db->data['m2_fundamental_observations'][$i]!==$r)throw new RuntimeException('old_changed'); echo json_encode([$a['observations'],$a['current'],$b['observations'],$b['current']]);"
            baseline=plan();baseline['observations']=[r for r in baseline['observations'] if r['metric_key']!='revenue']
            # Rebuild evidence to match the reduced baseline facts.
            doc=json.loads(baseline['evidence_json']);doc['facts']=[f for f in doc['facts'] if f['metric_key']!='revenue']
            for i,(f,r) in enumerate(zip(doc['facts'],baseline['observations'])):r['field_path']=f'evidence:facts/{i};source={f["position"]}'
            rawbase=sec.encode(doc);baseline['evidence_json']=rawbase.decode();baseline['stored_evidence']['sha256']=baseline['archive']['sha256']=hashlib.sha256(rawbase).hexdigest();baseline['stored_evidence']['bytes']=baseline['archive']['bytes']=len(rawbase)
            result=subprocess.run(['php','-r',php],input=json.dumps([baseline,qualified]),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr+result.stdout);self.assertEqual(json.loads(result.stdout),[2,1,0,0])
            for field,value in [('control_usd','999'),('start','2024-01-01')]:
                badmapping=copy.deepcopy(mapping);badmapping['revenue_reviews'][0][field]=value
                with self.assertRaisesRegex(ValueError,'SEC_REVENUE_REVIEW'):
                    sec.parse(raw,meta,dict(isin=profile['isin']),badmapping,profile['years'],revenue_only=True)
            # A competing total with another amount cannot silently win.
            gaap[tag]['units']['USD'][0]['val']+=1
            bad=json.dumps(data).encode();badmeta=dict(meta,bytes=len(bad),sha256=hashlib.sha256(bad).hexdigest())
            with self.assertRaisesRegex(ValueError,'SEC_CONFLICTING_REVENUE_TAGS'):
                sec.parse(bad,badmeta,dict(isin=profile['isin']),mapping,profile['years'],revenue_only=True)



if __name__=='__main__':unittest.main()
