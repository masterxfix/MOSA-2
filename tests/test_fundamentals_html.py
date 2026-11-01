import copy
from contextlib import nullcontext
import hashlib
import json
import subprocess
import unittest
from unittest.mock import patch
from scripts.fundamentals import droneshield_html as adapter, reports
from scripts.fundamentals.html_evidence import evidence
from scripts import fundamentals_pilot_once as shared
from scripts.market_collector.contracts import TransportResponse
from test_fundamentals_pilot import plan as annual, OBSERVED, PilotTests
from test_fundamentals_generic import zeiss_plan
archive_test=PilotTests.test_private_archive_exclusive_durable_readback_and_tamper_rejection

# Entirely invented values, no provider requests or fixtures copied from an issuer.
ROWS=[('Revenue','123.4','101.2'),('EBITDA','12.3','(4.5)'),('Underlying EBITDA','18.7','8.1'),
      ('Underlying Profit Before Tax','15.2','4.3'),('Profit After Tax','10.2','2.4'),
      ('Customer Cash Receipts','140.2','99.8'),('Operational Cashflow','16.4','(6.2)'),('Cash and Term Deposits','77.7','55.5')]
HTML='''<html><h1>DroneShield Limited Annual Report 2025</h1><p>Year ended 31 December 2025. All amounts in Australian dollars.</p>
<h2>Financial Highlights</h2><table><tr><th>AUD million</th><th>FY2025</th><th>FY2024</th></tr>'''+''.join(
    f'<tr><td>{k}</td><td>{a}</td><td>{b}</td></tr>' for k,a,b in ROWS)+'''</table>
<h2>Consolidated statement of profit or loss and other comprehensive income</h2><table>
<tr><th>AUD</th><th>2025</th><th>2024</th></tr><tr><td>Revenue</td><td>123,456,789</td><td>101,234,567</td></tr>
<tr><td>Profit after income tax expense for the year</td><td>10,234,567</td><td>2,456,789</td></tr></table></html>'''


def plan(html=HTML):
    raw=html.encode('utf-8');p=adapter.parse(raw,OBSERVED)
    meta=dict(url=adapter.URL,observed_at=OBSERVED,http_status=200,content_type='text/html',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    compact,stored=evidence(p,meta,dict(isin=adapter.ISIN,name='DroneShield'))
    p.update(metadata=meta,stored_evidence=stored,archive=dict(storage_key='/private/synthetic/evidence.json',sha256=stored['sha256'],bytes=len(compact),durable=True))
    return p


class HtmlTests(unittest.TestCase):
    def test_precise_statements_periods_units_and_evidence(self):
        p=plan();self.assertEqual(len(p['observations']),14)
        facts={(r['metric_key'],r['fiscal_year']):r for r in p['observations']}
        self.assertEqual(facts['revenue','2025']['value_decimal'],'123.456789')
        self.assertEqual(facts['ebitda','2024']['value_decimal'],'-4.5')
        self.assertEqual(facts['ebitda_underlying','2025']['value_decimal'],'18.7')
        self.assertEqual({r['period_start'] for r in facts.values()},{'2025-01-01','2024-01-01'})
        self.assertEqual({r['period_end'] for r in facts.values()},{'2025-12-31','2024-12-31'})
        self.assertNotEqual(p['metadata']['sha256'],p['stored_evidence']['sha256'])
        doc=json.loads(p['evidence_json']);self.assertFalse(doc['source_response']['retained'])
        self.assertNotIn('<html',p['evidence_json']);self.assertNotIn('77.7',p['evidence_json'])
        self.assertEqual(hashlib.sha256(p['evidence_json'].encode()).hexdigest(),p['archive']['sha256'])
        self.assertTrue(all(f['position'].startswith('html:table=') for f in doc['facts']))
        self.assertEqual(len(plan(HTML.replace('AUD million','AUD million').replace('<td>12.3</td>','<td>$12.3</td>'))['observations']),14)

    def test_invalid_identity_currency_period_columns_and_conflict(self):
        for html in [HTML.replace('DroneShield Limited','Other Limited'),HTML.replace('Australian dollars','US dollars'),
                     HTML.replace('31 December 2025','30 June 2025'),HTML.replace('FY2024','FY2023').replace('>2024<','>2023<'),
                     HTML.replace('</table>', '<tr><td>EBITDA</td><td>999</td><td>888</td></tr></table>',1)]:
            with self.subTest(case=html[:30]), self.assertRaises(ValueError):plan(html)
        missing=HTML.replace('<td>18.7</td>','<td>N/A</td>')
        self.assertNotIn('ebitda_underlying',{m['metric_key'] for m in plan(missing)['metrics']})
        script=HTML+'<script>secret unneeded page text</script>'
        self.assertNotIn('secret',plan(script)['evidence_json'])

    def test_shared_database_hash_distinction_atomicity_replay_and_readback(self):
        result=subprocess.run(['php','tests/fundamentals_html.php'],input=json.dumps([annual(),zeiss_plan(),plan()]),text=True,capture_output=True,cwd=shared.ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(result.stderr,'')
        self.assertTrue(json.loads(result.stdout)['ok'])

    def test_shared_pipeline_sends_only_evidence_and_one_get(self):
        selected=reports.selection(['droneshield-html-fy-2025'])[0]
        env=dict(GITHUB_SHA='a'*40);events=[];payloads=[]
        def archive(transport,action,env,identity=None,metadata=None,payload=None,selected=None):
            events.append(action)
            if action=='reserve':return dict(identity={})
            if payload is not None:payloads.append(payload)
            return dict(sha256=metadata['sha256'],bytes=metadata['bytes'],storage_key='/private/evidence.json',durable=True)
        def database(env,port,action,**kwargs):
            events.append(action)
            if action=='inspect':return dict(baseline={},protected={},asset_id='103'),0
            self.assertNotIn('<html',kwargs['plan']['evidence_json'])
            return dict(ok=True,readback='PASS'),0
        response=TransportResponse(HTML.encode(),OBSERVED,200,'text/html')
        with patch.object(shared,'guard'),patch.object(shared,'no_other_runs'),patch.object(shared.access,'configuration'), \
             patch.object(shared.access,'ssh_client',return_value=nullcontext(object())),patch.object(shared.access,'tunnel',return_value=nullcontext(3306)), \
             patch.object(shared,'archive',side_effect=archive),patch.object(shared,'database',side_effect=database), \
             patch.object(shared,'ReadOnlyHttpTransport') as transport:
            transport.return_value.fetch.return_value=response
            transport.return_value.attempt_count=1;transport.return_value.request_started_at=OBSERVED
            result=shared.execute(env,selected)
            self.assertTrue(result['ok'],result);self.assertEqual(transport.return_value.fetch.call_count,1)
        self.assertEqual(events,['inspect','reserve','archive','verify','apply','verify'])
        self.assertEqual(len(payloads),1);self.assertEqual(json.loads(payloads[0])['kind'],'derived_evidence')
        self.assertEqual(result['original_responses'],0);self.assertEqual(result['full_responses_archived'],0)

    def test_private_evidence_exclusive_hash_and_tamper(self):
        archive_test(self,derived=True)

del PilotTests
