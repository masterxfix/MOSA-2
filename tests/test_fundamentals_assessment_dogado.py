import json,os,stat,sys,re,hashlib,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from datetime import datetime,timezone
from scripts.fundamentals_assessment_once import PRICE
from scripts.fundamentals.assessment import prepare
from test_fundamentals_assessment_once import snapshot
from test_fundamentals_assessment import response

class DogadoTests(unittest.TestCase):
 def scope(self):
  scope=dict(__name__='fixture',os=os,stat=stat,sys=sys,json=json,re=re,UID=10317,GID=1003)
  exec(Path('scripts/fundamentals/assessment_dogado_remote.py').read_text(),scope)
  return scope
 def data(self):
  s=snapshot();s['current_observation_ids']=[f['observation_id'] for f in s['facts'] if f['end']=='2025-12-31'];return dict(snapshot=s,price=PRICE,invocation_id='synthetic-dogado',modules={n:Path('scripts/fundamentals/'+n+'.py').read_text() for n in ('assessment','responses_transport')},marker=dict(execution='fundamentals-ai-droneshield-dogado-20261101-01',commit='a'*40,isin='AU000000DRO2',model='gpt-6.1-sol',input_digest=prepare(s)[1],workflow='.github/workflows/fundamentals-assessment-dogado-once.yml'))
 def test_server_side_validated_success_key_never_returned(self):
  scope=self.scope();data=self.data();events=[]
  scope['existing_key']=lambda:dict(key='synthetic-local-key',hash='synthetic-config-hash')
  scope['reserve_ai']=lambda marker:events.append('marker')
  real_loader=scope['load_modules']
  def modules(bundle):
   a,t=real_loader(bundle)
   class Fake:
    def __init__(self,key,**kw):self.assert_key=key
    def __call__(self,request,**kwargs):
     events.append('post');return response(request)
   t.OpenAIResponsesTransport=Fake;return a,t
  scope['load_modules']=modules
  r=scope['dogado_pilot'](data)
  self.assertTrue(r['ok'],r);self.assertEqual(events,['marker','post']);self.assertEqual(r['model_calls'],1)
  self.assertFalse(r['key_transferred']);self.assertNotIn('synthetic-local-key',json.dumps(r));self.assertNotIn('factual_claims',r)
 def test_missing_exact_config_stops_before_marker_or_post(self):
  scope=self.scope();scope['existing_key']=Mock(side_effect=RuntimeError('CONFIG_NOT_VISIBLE_OR_READABLE'));scope['reserve_ai']=Mock()
  r=scope['dogado_pilot'](self.data());self.assertFalse(r['ok']);self.assertEqual(r['error_code'],'CONFIG_NOT_VISIBLE_OR_READABLE');self.assertEqual(r['model_calls'],0);scope['reserve_ai'].assert_not_called()
 def test_config_permission_and_php_failure_are_safe(self):
  scope=self.scope()
  from types import SimpleNamespace
  scope['os']=SimpleNamespace(O_RDONLY=0,O_NOFOLLOW=1,open=Mock(side_effect=PermissionError('private path not to publish')))
  with self.assertRaisesRegex(RuntimeError,'^CONFIG_NOT_VISIBLE_OR_READABLE$'):scope['existing_key']()
  self.assertEqual(scope['CONFIG'],'/var/www/vhosts/web213.server10.configcenter.info/httpdocs/scharwerk.de/dashboard_neu/data/private/openai_config.php')
  code=Path('scripts/fundamentals/assessment_dogado_remote.py').read_text();self.assertNotIn('listdir',code);self.assertNotIn('glob(',code)
 def test_fileless_package_and_workflow_without_api_secret(self):
  scope=self.scope();a,t=scope['load_modules'](self.data()['modules']);self.assertEqual(a.DEFAULTS['model'],'gpt-6.1-sol')
  code=Path('.github/workflows/fundamentals-assessment-dogado-once.yml').read_text()
  self.assertNotIn('MOSA2_OPENAI_API_KEY',code);self.assertIn('github.run_number == 1',code)

 def test_php_loader_syntax_without_reading_configuration(self):
  import subprocess
  scope=self.scope()
  result=subprocess.run(['php','-n','-r','if(false){'+scope['PHP_KEY']+'}'],capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,b'')
