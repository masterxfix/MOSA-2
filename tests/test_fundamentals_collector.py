import copy
import hashlib
import json
import subprocess
import unittest
from unittest.mock import patch
from scripts.fundamentals import pne, pne_quarter as adapter, reports
from scripts import fundamentals_collect as collector
from test_fundamentals_pilot import plan as annual, OBSERVED, PilotTests
from test_fundamentals_generic import zeiss_plan

# Wholly synthetic values. No provider access or production data.
HTML='''<html><h1>Quartalsergebnis: PNE AG startet gut in das Jahr 2026</h1>
<p>Cuxhaven, 13. Mai 2026 – Die PNE AG hat im ersten Quartal 2026 gute Ergebnisse erzielt.</p>
<p>Die Gesamtleistung lag bei 123,4 Mio. Euro (Vorjahr: 111,2 Mio. Euro).</p>
<p>Die Umsatzerlöse stiegen auf 54,3 Mio. Euro (Vorjahr: 42,1 Mio. Euro).</p>
<p>Das normalisierte EBITDA (normalised EBITDA) erreichte 12,3 Mio. Euro (Vorjahr: 10,1 Mio. Euro).</p>
<p>Das Betriebsergebnis (EBIT) betrug -4,3 Mio. Euro (Vorjahr: -6,2 Mio. Euro).</p>
<p>Für das Gesamtjahr 2026 erwartet PNE ein normalisiertes EBITDA von 987 Mio. Euro.</p></html>'''

def quarter(html=HTML):
    raw=html.encode();p=adapter.parse(raw,OBSERVED)
    p['metadata']=dict(url=adapter.URL,observed_at=OBSERVED,http_status=200,content_type='text/html',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    p['archive']=dict(storage_key='/private/synthetic/q1.body',sha256=p['metadata']['sha256'],bytes=len(raw),durable=True)
    return p

class CollectorTests(unittest.TestCase):
    def test_quarter_evidence_catalog_and_prior_period(self):
        p=quarter();self.assertEqual(len(p['observations']),8)
        self.assertEqual({r['period_end'] for r in p['observations']},{'2026-03-31','2025-03-31'})
        self.assertEqual({r['period_type'] for r in p['observations']},{'fq'})
        text=pne.normalized_text(HTML.encode())
        for row in p['observations']:
            a,b=map(int,row['field_path'].split(';')[0].split(':')[1:])
            self.assertEqual(pne.number(text[a:b]),row['value_decimal'])
        old={m['metric_key']:m for p0 in [annual(),zeiss_plan()] for m in p0['metrics']}
        for metric in p['metrics']:self.assertEqual(metric,old[metric['metric_key']])

    def test_missing_values_forecasts_duplicates_and_conflicts(self):
        html=HTML.replace('54,3 Mio. Euro (Vorjahr: 42,1 Mio. Euro)','nicht verfügbar')
        self.assertEqual(len(quarter(html)['observations']),6)
        self.assertEqual(quarter(html)['unqualified_metrics'][0]['metric_key'],'revenue')
        self.assertEqual(len(quarter(HTML.replace('(Vorjahr: 42,1 Mio. Euro)',''))['observations']),7)
        repeated=HTML.replace('</html>','<p>Die Gesamtleistung lag bei 123,4 Mio. Euro (Vorjahr: 111,2 Mio. Euro).</p></html>')
        self.assertEqual(len(quarter(repeated)['observations']),8)
        for html in [HTML.replace('13. Mai','14. Mai'),HTML.replace('123,4 Mio. Euro','123,4 Mrd. Euro'),
                     repeated.replace('lag bei 123,4','lag bei 999,9',1),HTML.replace('ersten Quartal 2026','zweiten Quartal 2026')]:
            with self.assertRaises(ValueError):quarter(html)
        self.assertNotIn('987',[r['value_decimal'] for r in quarter()['observations']])

    def test_fy_fq_two_assets_atomicity_readback_and_replays(self):
        result=subprocess.run(['php','tests/fundamentals_collector.php'],input=json.dumps([annual(),zeiss_plan(),quarter()]),text=True,capture_output=True,cwd=collector.shared.ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(result.stderr,'')
        self.assertTrue(json.loads(result.stdout)['ok'])

    def test_manual_authority_and_sequential_stop(self):
        env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_RUN_ATTEMPT='1',GITHUB_SHA='a'*40,EXPECTED_COMMIT='a'*40,AUTHORIZATION='MOSA2-REPORTS-pne-q1-2026:'+'a'*40)
        calls=[]
        def fake(e,r):calls.append(r);return dict(ok=True,provider_requests=1)
        self.assertTrue(collector.collect(env,['pne-q1-2026'],fake)['ok']);self.assertEqual(len(calls),1)
        for keys in [[],['pne-fy-2025'],['pne-q1-2026']*2]:
            with self.assertRaises(ValueError):collector.collect(env,keys,fake)
        with self.assertRaises(ValueError):collector.collect(env|{'GITHUB_RUN_ATTEMPT':'2'},['pne-q1-2026'],fake)
        keys=['pne-q1-2026','zeiss-fy-2025'];env['AUTHORIZATION']='MOSA2-REPORTS-'+','.join(keys)+':'+'a'*40
        with patch.object(collector,'APPROVED_REPORTS',tuple(keys)):
            calls.clear();self.assertTrue(collector.collect(env,keys,fake)['ok']);self.assertEqual(len(calls),2)
            calls.clear()
            def fail(e,r):calls.append(r);return dict(ok=False,provider_requests=1,outcome='UNKNOWN_NO_RETRY')
            self.assertFalse(collector.collect(env,keys,fail)['ok']);self.assertEqual(len(calls),1)

# Only the unchanged transport/archive proofs relevant to the new shared path.
class ExistingBoundaries(unittest.TestCase):
    test_one_request_is_consumed_on_error=PilotTests.test_one_request_is_consumed_on_error
    test_private_archive_exclusive_durable_readback_and_tamper_rejection=PilotTests.test_private_archive_exclusive_durable_readback_and_tamper_rejection

# Do not load the imported full legacy suite redundantly.
del PilotTests
