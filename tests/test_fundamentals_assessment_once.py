import json,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import Mock,patch
from scripts import fundamentals_assessment_once as pilot
from scripts.fundamentals import assessment as a
from scripts.fundamentals.analysis import build
from scripts.fundamentals.curated import load
from test_fundamentals_analysis import fact
from test_fundamentals_assessment import response

# Manifest is used only for offline sizing; live runner reads Dogado, never this fixture.
def snapshot():
 p=load(Path('scripts/fundamentals/manifests/droneshield-fy2025-v1.json').read_bytes(),'2026-11-01 14:00:00.000000',dict(isin='AU000000DRO2',name='DroneShield'))[0]
 rows=[]
 for i,r in enumerate(p['observations']):
  f=fact(i+1,r['metric_key'],r['value_decimal']);f.update(r);f.update(id=str(i+1),parser_key=p['parser_key'])
  rows.append(f)
 return build(dict(id='529',name='DroneShield',identifiers=[dict(normalized_value='AU000000DRO2')],facts=rows,current={},market_sources=[]),[dict(id=1,source_type='manually_reviewed_public_facts')])

class PilotTests(unittest.TestCase):
 def test_full_echo_budget_and_prepost_reservation_order(self):
  events=[];s=snapshot();_,sha=a.prepare(s)
  def preflight(req,budget,p,meta):
   self.assertEqual(req['service_tier'],'default');self.assertEqual(req['max_output_tokens'],4000)
   self.assertLessEqual(float(budget['max_cost_usd']),0.10);events.append('reserve')
  def post(req,**kw):events.append('post');return response(req)
  result=a.ResponsesAdapter(post,max_output_tokens=4000).assess(s,price=pilot.PRICE,now=datetime.now(timezone.utc),simulate=True,preflight=preflight)
  self.assertTrue(result['simulated']);self.assertEqual(events,['reserve','post'])
 def test_marker_failure_prevents_post_and_missing_secret_prevents_access(self):
  s=snapshot();post=Mock()
  with self.assertRaisesRegex(a.AssessmentError,'MARKER_FAILED'):
   a.ResponsesAdapter(post).assess(s,price=pilot.PRICE,now=datetime.now(timezone.utc),simulate=True,preflight=lambda *args:(_ for _ in ()).throw(a.AssessmentError('MARKER_FAILED')))
  post.assert_not_called()
  with patch.object(pilot.shared,'guard'),patch.object(pilot.shared,'no_other_runs') as access:
   r=pilot.execute(dict(GITHUB_WORKFLOW_REF='masterxfix/MOSA-2/.github/workflows/fundamentals-assessment-once.yml@refs/heads/main'))
   self.assertEqual(r['error_code'],'SECRET_MISSING');self.assertEqual(r['model_calls'],0);access.assert_not_called()
 def test_exclusive_marker_binding_and_readback(self):
  import hashlib
  scope={'__name__':'fixture','EXECUTIONS':set(),'ROOT':'fixed','BASE':'fixedbase','re':__import__('re'),'json':json,'hashlib':hashlib}
  class OS:
   def umask(self,v):pass
   def close(self,fd):pass
  scope.update(os=OS(),need=lambda ok,code:None if ok else (_ for _ in ()).throw(ValueError(code)),checked=lambda d:{'fixedbase':[1,2]},checked_fd=lambda *a,**kw:1)
  files={}
  def create(fd,name,raw):
   if name in files:raise FileExistsError()
   files[name]=raw
  scope.update(create_file=create,read_file=lambda fd,name:files[name])
  exec(Path('scripts/fundamentals/assessment_once_remote.py').read_text(),scope)
  d=dict(execution=scope['AI_ONCE'],commit='a'*40,isin='AU000000DRO2',model='gpt-6.1-sol',input_digest='b'*64,workflow='.github/workflows/fundamentals-assessment-once.yml')
  self.assertTrue(scope['reserve_ai'](d)['reserved']);self.assertEqual(len(files),1)
  with self.assertRaises(FileExistsError):scope['reserve_ai'](d)
  self.assertIn(b'bbbbbbbb',next(iter(files.values())))
