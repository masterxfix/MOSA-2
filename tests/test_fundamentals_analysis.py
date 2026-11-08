import unittest
from scripts.fundamentals.analysis import build

def fact(id,metric,value,year=2025,kind='fy',currency='AUD',unit='AUD_MILLION'):
 return dict(id=str(id),metric_key=metric,value_decimal=value,period_type=kind,fiscal_year=year,fiscal_quarter=None if kind=='fy' else 1,period_start=f'{year}-01-01',period_end=f'{year}-12-31' if kind=='fy' else f'{year}-03-31',unit_key=unit,unit_version=1,source_id=1,monetary_currency_code=currency,scale_numerator='1000000',scale_denominator='1',parser_key='curated_public_facts_v1',parse_status='parsed',fetch_id=1,field_path='curated-evidence:facts/0',evidence_sha256='a'*64)
def php_wire(asset):
 import subprocess,json
 result=subprocess.run(['php','-r',"require 'scripts/fundamentals/analysis_read.php'; $assets=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR); echo json_encode(analysisWireAssets($assets),JSON_THROW_ON_ERROR);"],input=json.dumps([asset]),text=True,capture_output=True)
 if result.returncode or result.stderr:raise AssertionError(result.stderr)
 return json.loads(result.stdout)[0]
def snapshot(rows):
 return build(php_wire(dict(id='1',name='Synthetic',identifiers=[dict(normalized_value='AU000000DRO2')],facts=rows,current={},market_sources=[])),[dict(id=1,source_type='manually_reviewed_public_facts'),dict(id=2,source_type='issuer_release')])
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
  for changed in [dict(period_type='fq',fiscal_quarter=1,period_end='2025-03-31'),dict(monetary_currency_code='EUR',unit_key='EUR_MILLION'),dict(unit_key='AUD'),dict(source_id=2)]:
   a=fact(1,'revenue','100',2024);b=fact(2,'revenue','200');b.update(changed)
   self.assertEqual(snapshot([a,b])['calculations'],[])
 def test_bound_queries_and_etf_filter(self):
  from pathlib import Path
  s=Path('scripts/fundamentals/analysis_read.php').read_text()
  self.assertIn("$a['asset_class']!=='equity'",s);self.assertIn('LIMIT 257',s);self.assertIn('TRANSACTION READ ONLY',s)

 def test_single_isin_read_mode_contract(self):
  from pathlib import Path
  from scripts import fundamentals_analysis_once as runner
  self.assertEqual(runner.target_isin({'MOSA_ANALYSIS_ISIN':'NO0010081235'}),'NO0010081235')
  with self.assertRaisesRegex(ValueError,'ANALYSIS_ISIN'):
   runner.target_isin({'MOSA_ANALYSIS_ISIN':'NO001008123X'})
  reader=Path('scripts/fundamentals/analysis_read.php').read_text()
  workflow=Path('.github/workflows/fundamentals-analysis.yml').read_text()
  self.assertIn("'m2_market_current'",reader)
  self.assertIn("'market_data_read'=>!$targeted",reader)
  self.assertIn('MOSA_ANALYSIS_ISIN: ${{ inputs.isin }}',workflow)

 def test_binary_json_failure_and_explicit_projection(self):
  import subprocess,json
  r=subprocess.run(['php','-r',"try{json_encode(['period_key'=>hex2bin(str_repeat('ff',32))],JSON_THROW_ON_ERROR);}catch(JsonException $e){echo $e->getCode();}"],capture_output=True,text=True)
  self.assertEqual(r.stdout,'5')
  r=subprocess.run(['php','-r',"echo json_encode(['evidence_sha256'=>strtoupper(bin2hex(hex2bin(str_repeat('ff',32))))],JSON_THROW_ON_ERROR);"],capture_output=True,text=True)
  self.assertEqual(json.loads(r.stdout)['evidence_sha256'],'FF'*32)
  from pathlib import Path
  sql=Path('scripts/fundamentals/analysis_read.php').read_text()
  self.assertNotIn('SELECT o.*',sql);self.assertIn('HEX(fi.sha256)',sql)
  self.assertIn('SELECT metric_key,period_type,observation_id',sql)
 def test_current_reference_rejected(self):
  a=dict(id='1',name='Test',identifiers=[],facts=[fact(1,'revenue','1')],current={'ebitda:fy':[dict(observation_id='1')]},market_sources=[])
  with self.assertRaisesRegex(ValueError,'CURRENT_REFERENCE'):build(a,[dict(id=1,source_type='issuer_release')])
 def test_safe_phases_and_output(self):
  from scripts import fundamentals_analysis_once as runner
  from unittest.mock import patch
  from pathlib import Path
  for phase in runner.PHASES:
   self.assertNotIn('password',phase)
  with patch.object(runner.shared,'guard',side_effect=RuntimeError('private secret sql path')):
   result=runner.execute({});self.assertNotIn('private',str(result));self.assertEqual(result['error_code'],'SAFE_PHASE_FAILURE')
  code=Path('scripts/fundamentals_analysis_once.py').read_text()
  self.assertNotIn("facts=s['facts']",code);self.assertNotIn('registered_sources_not_asset_availability',code)
 def test_existing_issuer_plans_same_contract(self):
  from test_fundamentals_pilot import plan
  from test_fundamentals_generic import zeiss_plan
  from scripts.fundamentals.curated import load
  from pathlib import Path
  curated=load(Path('scripts/fundamentals/manifests/droneshield-fy2025-v1.json').read_bytes(),'2026-11-01 14:00:00.000000',dict(isin='AU000000DRO2',name='DroneShield'))[0]
  for p in [plan(),zeiss_plan(),curated]:
   rows=[]
   for i,r in enumerate(p['observations']):
    f=fact(i+1,r['metric_key'],r['value_decimal']);f.update(r);f.update(id=str(i+1),parser_key=p['parser_key'])
    u=next(u for u in p['units'] if u['unit_key']==r['unit_key'])
    for k in ['scale_numerator','scale_denominator','monetary_currency_code']:f[k]=u[k]
    rows.append(f)
   s=snapshot(rows);self.assertEqual(len(s['facts']),len(rows));self.assertEqual(s['contract'],'mosa2-ai-analysis-input-v1')

 def test_php_empty_and_populated_current_roundtrip(self):
  import subprocess,json
  raw=subprocess.check_output(['php','-r',"echo json_encode(['current'=>[]],JSON_THROW_ON_ERROR);"])
  old=json.loads(raw)['current'];self.assertIsInstance(old,list)
  asset=dict(id='1',name='Synthetic',identifiers=[],facts=[],current=old,market_sources=[])
  with self.assertRaisesRegex(ValueError,'CURRENT_SHAPE'):build(asset,[])
  fixed=php_wire(asset);self.assertEqual(fixed['current'],{});self.assertIsInstance(fixed['current'],dict)
  s=build(fixed,[]);self.assertIn('revenue',s['missing_metrics']);self.assertIn(dict(code='NO_QUALIFIED_FUNDAMENTALS'),s['warnings'])
  asset['facts']=[fact(1,'revenue','123')];asset['current']={'revenue:fy':[dict(observation_id='1')]}
  s=build(php_wire(asset),[dict(id=1,source_type='issuer_release')]);self.assertEqual(s['current_observation_ids'],['1'])
 def test_validated_error_classes(self):
  from scripts.fundamentals.analysis import SnapshotError
  import copy
  asset=php_wire(dict(id='1',name='Synthetic',identifiers=[],facts=[fact(1,'revenue','1')],current={},market_sources=[]))
  sources=[dict(id=1,source_type='issuer_release')]
  for field,value,code in [('current',[],'CURRENT_SHAPE'),('facts',{},'FACT_SHAPE')]:
   bad=copy.deepcopy(asset);bad[field]=value
   with self.assertRaisesRegex(SnapshotError,code):build(bad,sources)
  for field,value,code in [('period_start','invalid','PERIOD_INVALID'),('value_decimal','NaN','DECIMAL_INVALID'),('source_id',99,'SOURCE_REFERENCE')]:
   bad=copy.deepcopy(asset);bad['facts'][0][field]=value
   with self.assertRaisesRegex(SnapshotError,code):build(bad,sources)
  with self.assertRaisesRegex(SnapshotError,'SOURCE_REFERENCE'):build(asset,[])
