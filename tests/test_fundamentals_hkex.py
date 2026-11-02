"""Offline HKEX adapter tests use invented one-page PDFs only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from scripts.fundamentals import hkex
from scripts.fundamentals.analysis import build

OBSERVED='2026-11-02 00:00:00.123456'


def php_executable():
    candidates=[shutil.which('php')]
    if os.name == 'nt':
        candidates.append(r'C:\php\php.exe')
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    location='PATH' if os.name != 'nt' else 'PATH or C:\\php\\php.exe'
    raise FileNotFoundError(f'PHP executable not found in {location}')


def fixture(unit="RMB'000", years=('2025','2024'), company='BYD Company Limited',
            standard=True, consolidated=True):
    texts=[(40,800,'Annual Report 2025'),(40,780,company),(40,760,'31 December 2025'),
           (40,740,unit),(40,720,'PRC Accounting Standards for Business Enterprises' if standard else 'Other Standard'),
           (40,700,'consolidated and company financial statements' if consolidated else 'separate financial statements'),
           (40,670,'Consolidated Income Statement'),(40,650,'31 December 2025'),(40,630,unit),
           (40,610,'Note V'),(460,610,years[0]),(520,610,years[1])]
    rows=[('I. Operating revenue','803964958','777102455'),('II. Operating profit','40184709','50486047'),
          ('III. Total profit','39753049','49680677'),('IV. Net profit','33760758','41587940')]
    for i,(label,a,b) in enumerate(rows):
        y=585-i*22;texts.extend([(40,y,label),(460,y,a),(520,y,b)])
    y=470;texts.extend([(40,y,'Consolidated Cash Flow Statement'),(40,y-20,'For 2025'),(40,y-40,unit),
        (40,y-60,'Note V'),(460,y-60,years[0]),(520,y-60,years[1]),
        (40,y-85,'Net cash flow from operating activities'),(460,y-85,'59135544'),(520,y-85,'133453873')])
    def escape(t):return t.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
    stream='\n'.join(f'BT /F1 10 Tf 1 0 0 1 {x} {y} Tm ({escape(t)}) Tj ET' for x,y,t in texts).encode('utf-8')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 820] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        f'<< /Length {len(stream)} >>\nstream\n'.encode()+stream+b'\nendstream']
    data=b'%PDF-1.4\n';offsets=[0]
    for i,obj in enumerate(objects,1):offsets.append(len(data));data+=f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(data);data+=f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    data+=b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return data+f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def plan(raw=None, observed_at=OBSERVED):
    raw=raw or fixture();profile=hkex.profile_for('byd-company-fy2025')
    meta=dict(url=profile['url'],observed_at=observed_at,http_status=200,content_type='application/pdf',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    p=hkex.parse(raw,meta,profile)
    p['archive']=dict(storage_key='/private/mosa2/hkex/byd-company-fy2025/evidence.json',sha256=p['stored_evidence']['sha256'],bytes=p['stored_evidence']['bytes'],durable=True)
    return p


class HkexTests(unittest.TestCase):
    def test_catalog_definitions_reuse_existing_keys_without_operating_profit_aliasing(self):
        from scripts.fundamentals import sec_xbrl, zeiss
        self.assertEqual(hkex.DEFINITIONS['revenue'][:2],zeiss.DEFINITIONS['revenue'][:2])
        self.assertEqual(hkex.DEFINITIONS['profit_before_tax'][:2],zeiss.DEFINITIONS['profit_before_tax'][:2])
        self.assertEqual(hkex.DEFINITIONS['profit_after_tax'][:2],sec_xbrl.DEFS['profit_after_tax'][:2])
        self.assertEqual(hkex.DEFINITIONS['operating_cashflow'][:2],sec_xbrl.DEFS['operating_cashflow'][:2])
        self.assertNotEqual(hkex.DEFINITIONS['operating_profit'][:2],('IFRS Operating Profit / Loss','Reported consolidated IFRS profit or loss from operating activities; not assumed equivalent to EBIT or EBITDA.'))
        self.assertNotEqual(hkex.DEFINITIONS['operating_profit'][:2],('Operating Income / Loss','Reported consolidated US-GAAP operating income or loss; not assumed equivalent to EBIT.'))

    def test_adapter_values_units_and_evidence(self):
        p=plan();self.assertEqual(len(p['observations']),10);self.assertEqual({r['unit_key'] for r in p['observations']},{'CNY_THOUSAND'})
        self.assertEqual([r['value_decimal'] for r in p['observations'][:4]],['803964958','777102455','40184709','50486047'])
        self.assertEqual(p['units'][0]['monetary_currency_code'],'CNY');self.assertEqual(p['units'][0]['scale_numerator'],'1000')
        doc=json.loads(p['evidence_json']);self.assertEqual(len(doc['facts']),10);self.assertTrue(all(f['position'].startswith('pdf:page=1;') for f in doc['facts']))

    def test_negative_profile_source_unit_year_scope_and_wrong_identity(self):
        base=fixture()
        with self.assertRaises(ValueError): hkex.parse(base,dict(url='https://wrong.invalid',http_status=200,content_type='application/pdf',bytes=len(base),sha256=hashlib.sha256(base).hexdigest(),observed_at=OBSERVED),hkex.profile_for('byd-company-fy2025'))
        bad_unit=fixture(unit='HKD million');with_unit=self._meta(bad_unit)
        with self.assertRaises(ValueError): hkex.parse(bad_unit,with_unit,hkex.profile_for('byd-company-fy2025'))
        bad_year=fixture(years=('2024','2025'))
        with self.assertRaises(ValueError): hkex.parse(bad_year,self._meta(bad_year),hkex.profile_for('byd-company-fy2025'))
        bad_scope=fixture(consolidated=False)
        with self.assertRaises(ValueError): hkex.parse(bad_scope,self._meta(bad_scope),hkex.profile_for('byd-company-fy2025'))
        bad=copy.deepcopy(hkex.profile_for('byd-company-fy2025'));bad['isin']='CNE100000000'
        with self.assertRaises(ValueError): hkex.parse(base,self._meta(base),bad)

    @staticmethod
    def _meta(raw):
        p=hkex.profile_for('byd-company-fy2025')
        return dict(url=p['url'],observed_at=OBSERVED,http_status=200,content_type='application/pdf',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def test_php_writer_current_readback_replay_and_evidence_tamper(self):
        p=subprocess.run([php_executable(),'tests/fundamentals_hkex.php'],input=json.dumps([plan(),plan(observed_at='2026-11-02 00:00:01.123456')]),text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(p.returncode,0,f'php_exit={p.returncode} stderr={p.stderr[:320]!r} stdout={p.stdout[:320]!r}')
        self.assertEqual(p.stderr,'',f'php_stderr={p.stderr[:320]!r}')
        try:
            result=json.loads(p.stdout)
        except json.JSONDecodeError as error:
            self.fail(f'php_stdout_not_json line={error.lineno} column={error.colno} stdout_prefix={p.stdout[:320]!r}')
        self.assertEqual(result['replay'],'PASS')

    def test_analysis_input_contract_accepts_qualified_plan_shape(self):
        p=plan();facts=[];current={}
        for i,row in enumerate(p['observations'],1):
            facts.append(dict(id=str(i),metric_key=row['metric_key'],value_decimal=row['value_decimal'],unit_key=row['unit_key'],unit_version='1',
                period_type='fy',fiscal_year=row['fiscal_year'],fiscal_quarter=None,period_start=row['period_start'],period_end=row['period_end'],
                source_id='hkex',fetch_id='fetch',field_path=row['field_path'],evidence_sha256=p['stored_evidence']['sha256'],parser_key=p['parser_key'],
                parse_status='parsed',monetary_currency_code='CNY',scale_numerator='1000',scale_denominator='1'))
            if row['fiscal_year']=='2025': current[row['metric_key']+':fy']=[dict(observation_id=str(i))]
        asset=dict(id='103',name='BYD Company Limited',identifiers=[dict(normalized_value='CNE100000296')],facts=facts,current=current,market_sources=[])
        result=build(asset,[dict(id='hkex',source_type='exchange_annual_report')])
        self.assertEqual(result['contract'],'mosa2-ai-analysis-input-v1');self.assertEqual(len(result['facts']),10);self.assertEqual(result['warnings'].__class__,list)


if __name__=='__main__':unittest.main()
