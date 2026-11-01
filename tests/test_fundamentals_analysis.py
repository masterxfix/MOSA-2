import unittest
from scripts.fundamentals.analysis import build

def fact(id,metric,value,year=2025,kind='fy',currency='AUD',unit='AUD_MILLION'):
 return dict(id=str(id),metric_key=metric,value_decimal=value,period_type=kind,fiscal_year=year,fiscal_quarter=None if kind=='fy' else 1,period_start=f'{year}-01-01',period_end=f'{year}-12-31' if kind=='fy' else f'{year}-03-31',unit_key=unit,unit_version=1,source_id=1,monetary_currency_code=currency,scale_numerator='1000000',scale_denominator='1',parser_key='curated_public_facts_v1',parse_status='parsed',fetch_id=1,field_path='curated-evidence:facts/0',evidence_sha256='a'*64)
def snapshot(rows):return build(dict(id='1',name='Synthetic',identifiers=[dict(normalized_value='AU000000DRO2')],facts=rows,current={},market_sources=[]),[dict(id=1,source_type='manually_reviewed_public_facts')])
class AnalysisTests(unittest.TestCase):
 def test_growth_margin_and_references(self):
  s=snapshot([fact(1,'revenue','50',2024),fact(2,'revenue','200'),fact(3,'ebitda','10'),fact(4,'ebitda_underlying','30')])
  self.assertTrue(any(c['kind']=='growth_percent' and c['value']=='300' for c in s['calculations']))
  self.assertTrue(any(c['kind']=='margin_percent' and c['value']=='5.00' for c in s['calculations']))
  self.assertTrue(all(set(c['observation_ids'])<=set('1234') for c in s['calculations']))
  self.assertTrue(s['facts'][0]['rounded']);self.assertEqual(s['interpretations'],[])
 def test_negative_zero_and_missing(self):
  for v in ['-10','0']:
   s=snapshot([fact(1,'ebitda',v,2024),fact(2,'ebitda','5')]);self.assertFalse(any(c['kind']=='growth_percent' for c in s['calculations']))
  self.assertIn('revenue',snapshot([])['missing_metrics']);self.assertEqual(snapshot([])['facts'],[])
 def test_quarters_currency_units_sources_separate(self):
  for changed in [dict(period_type='fq'),dict(monetary_currency_code='EUR',unit_key='EUR_MILLION'),dict(unit_key='AUD'),dict(source_id=2)]:
   a=fact(1,'revenue','100',2024);b=fact(2,'revenue','200');b.update(changed)
   self.assertEqual(snapshot([a,b])['calculations'],[])
 def test_bound_queries_and_etf_filter(self):
  from pathlib import Path
  s=Path('scripts/fundamentals/analysis_read.php').read_text()
  self.assertIn("$a['asset_class']!=='equity'",s);self.assertIn('LIMIT 257',s);self.assertIn('TRANSACTION READ ONLY',s)
