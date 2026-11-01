"""Generated PDF bytes contain invented amounts only; never contact a provider."""
import copy
from decimal import Decimal
import hashlib
from io import BytesIO
import json
import subprocess
import unittest
from unittest.mock import patch
from scripts.fundamentals import droneshield as adapter
from scripts.fundamentals.pdf_document import read_pdf
from scripts import fundamentals_collect as collector
from test_fundamentals_pilot import plan as annual, OBSERVED
from test_fundamentals_generic import zeiss_plan

LABELS=['Revenue','EBITDA','Underlying EBITDA','Underlying Profit Before Tax','Profit After Tax','Customer Cash Receipts','Operating Cashflow']

def fixture(unit='AUD millions',missing=False,reverse=False,conflict=False,chart=True):
    texts=[(40,780,'DroneShield Limited'),(40,760,'Annual Report 2025'),(40,710,'Financial Highlights'),(40,690,unit),
           (320,660,'FY2024' if reverse else 'FY2025'),(420,660,'FY2025' if reverse else 'FY2024'),(520,660,'Change %')]
    for i,label in enumerate(LABELS):
        texts.extend([(40,630-i*25,label),(320,630-i*25,'N/A' if missing and i==2 else '1,234.5'),
                      (420,630-i*25,'(234.5)'),(520,630-i*25,'999%')])
    texts.extend([(40,455,'Cash and Term Deposits'),(320,455,'789.1'),(420,455,'678.2')])
    if conflict:texts.extend([(40,430,'Revenue'),(320,430,'9,999.9'),(420,430,'(234.5)')])
    if chart:texts.extend([(40,200,'Revenue chart'),(320,170,'7777'),(420,170,'8888')])
    def escape(t):return t.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
    stream='\n'.join(f'BT /F1 10 Tf 1 0 0 1 {x} {y} Tm ({escape(t)}) Tj ET' for x,y,t in texts).encode('ascii')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 820] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        f'<< /Length {len(stream)} >>\nstream\n'.encode()+stream+b'\nendstream']
    data=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(data));data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(data);data+=f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    data+=b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return data+f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()

def plan(raw=None):
    raw=raw or fixture();p=adapter.parse(raw,OBSERVED)
    p['metadata']=dict(url=adapter.URL,observed_at=OBSERVED,http_status=200,content_type='application/pdf',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    p['archive']=dict(storage_key='/private/synthetic/drone.pdf',sha256=p['metadata']['sha256'],bytes=len(raw),durable=True)
    return p

class PdfTests(unittest.TestCase):
    def test_pdf_table_years_units_negatives_and_provenance(self):
        p=plan();self.assertEqual(len(p['observations']),14)
        self.assertEqual({r['period_type'] for r in p['observations']},{'fy'})
        self.assertEqual({r['unit_key'] for r in p['observations']},{'AUD_MILLION'})
        self.assertEqual(p['units'][0]['monetary_currency_code'],'AUD')
        self.assertEqual(p['units'][0]['scale_numerator'],'1000000')
        for r in p['observations']:
            self.assertEqual(r['value_decimal'],'1234.5' if r['fiscal_year']=='2025' else '-234.5')
            self.assertEqual(r['period_start'],r['fiscal_year']+'-01-01')
            self.assertEqual(r['period_end'],r['fiscal_year']+'-12-31')
            self.assertIn('page=1;table=Financial Highlights',r['field_path'])
        self.assertIn('ebitda_underlying',{m['metric_key'] for m in p['metrics']})
        self.assertNotIn('ebitda_normalised',{m['metric_key'] for m in p['metrics']})
        old={m['metric_key']:m for p0 in [annual(),zeiss_plan()] for m in p0['metrics']}
        for m in p['metrics']:
            if m['metric_key'] in old:self.assertEqual(m,old[m['metric_key']])
        self.assertIn(dict(metric_key='cash_and_term_deposits',reason='POINT_IN_TIME_UNSUPPORTED'),p['unqualified_metrics'])

    def test_thousands_and_reversed_year_columns(self):
        p=plan(fixture(unit='AUD thousands',reverse=True))
        self.assertEqual(p['observations'][0]['fiscal_year'],'2024')
        self.assertEqual(p['observations'][0]['value_decimal'],'1.2345')
        self.assertEqual(p['observations'][1]['value_decimal'],'-0.2345')

    def test_missing_cell_and_chart_exclusion(self):
        p=plan(fixture(missing=True));self.assertEqual(len(p['observations']),13)
        self.assertIn(dict(metric_key='ebitda_underlying',reason='UNQUALIFIED_VALUE_CELL'),p['unqualified_metrics'])
        self.assertEqual(plan()['observations'],plan(fixture(chart=False))['observations'])
        self.assertIsNone(adapter.amount('45%','million'))
        self.assertEqual(adapter.amount('A$123.4m','million'),'123.4')
        self.assertEqual(adapter.amount('(A$123.4m)','million'),'-123.4')

    def test_fail_closed_identity_currency_unit_year_and_conflict(self):
        for raw in [b'<html/>',fixture().replace(b'DroneShield Limited',b'Other Corp Limited'),
                    fixture(unit='USD millions'),fixture(unit='AUD millions thousands'),
                    fixture().replace(b'FY2024',b'FY2023'),fixture(conflict=True)]:
            with self.assertRaises(ValueError):plan(raw)

    def test_php_validation_atomicity_existing_assets_and_readback(self):
        result=subprocess.run(['php','tests/fundamentals_pdf.php'],input=json.dumps([annual(),zeiss_plan(),plan()]),text=True,capture_output=True,cwd=collector.shared.ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(result.stderr,'')
        self.assertTrue(json.loads(result.stdout)['ok'])

    def test_one_shot_authority_pdf_archive_and_pipeline(self):
        env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_RUN_ATTEMPT='1',GITHUB_SHA='a'*40,EXPECTED_COMMIT='a'*40,AUTHORIZATION='MOSA2-REPORTS-droneshield-fy-2025:'+'a'*40)
        calls=[]
        def fake(e,r):calls.append(r);return dict(ok=True,provider_requests=1)
        self.assertTrue(collector.collect(env,['droneshield-fy-2025'],fake)['ok'])
        self.assertEqual(calls[0]['adapter'].CONTENT_TYPE,'application/pdf')
        with self.assertRaises(ValueError):collector.collect(env,['pne-q1-2026'],fake)
        with self.assertRaises(ValueError):collector.collect(env|{'GITHUB_RUN_ATTEMPT':'2'},['droneshield-fy-2025'],fake)
