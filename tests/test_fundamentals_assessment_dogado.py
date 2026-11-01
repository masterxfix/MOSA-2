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
  s=snapshot();s['current_observation_ids']=[f['observation_id'] for f in s['facts'] if f['end']=='2025-12-31'];return dict(snapshot=s,price=PRICE,invocation_id='synthetic-dogado',modules={n:Path('scripts/fundamentals/'+n+'.py').read_text() for n in ('assessment','responses_transport')},marker=dict(execution='fundamentals-ai-droneshield-protection-20261101-01',commit='a'*40,isin='AU000000DRO2',model='gpt-6.1-sol',input_digest=prepare(s)[1],workflow='.github/workflows/fundamentals-assessment-protection-once.yml'))
 def test_server_side_validated_success_key_never_returned(self):
  scope=self.scope();data=self.data();events=[]
  scope['existing_key']=lambda *args:dict(key='synthetic-local-key',hash='synthetic-config-hash')
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
  scope['protection_diagnosis']=Mock(side_effect=PermissionError('private path not to publish'))
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

 def test_python_php_identical_metadata_policy(self):
  import subprocess
  scope=self.scope();base=dict(type=stat.S_IFREG,uid=10317,gid=1003,mode=0o600,symlink=False,nlink=1)
  cases=[base,dict(base,gid=1002),dict(base,mode=0o640),dict(base,mode=0o640,gid=1002),dict(base,mode=0o644),dict(base,mode=0o660),dict(base,mode=0o400),dict(base,mode=0o4600),dict(base,uid=999),dict(base,symlink=True,type=stat.S_IFLNK),dict(base,nlink=2)]
  code=scope['PHP_POLICY']+"$rows=json_decode(stream_get_contents(STDIN),true);echo json_encode(array_map(fn($m)=>filePolicy($m,10317,1003),$rows));"
  r=subprocess.run(['php','-n','-r',code],input=json.dumps(cases),capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr)
  expected=[scope['file_policy'](m,10317,1003) for m in cases];self.assertEqual(json.loads(r.stdout),expected)
  self.assertEqual(expected[:2],['PASS','PASS']);self.assertEqual(expected[3],'CONFIG_GROUP_READ_UNTRUSTED');self.assertEqual(expected[4],'CONFIG_MODE')
  base=dict(type=stat.S_IFDIR,uid=0,gid=0,mode=0o755,symlink=False,nlink=2)
  cases=[base,dict(base,uid=10317,gid=1002,mode=0o710),dict(base,mode=0o777),dict(base,uid=999),dict(base,symlink=True),dict(base,type=stat.S_IFREG)]
  code=scope['PHP_POLICY']+"$rows=json_decode(stream_get_contents(STDIN),true);echo json_encode(array_map(fn($m)=>parentPolicy($m,10317),$rows));"
  r=subprocess.run(['php','-n','-r',code],input=json.dumps(cases),capture_output=True,text=True)
  self.assertEqual(json.loads(r.stdout),[scope['parent_policy'](m,10317) for m in cases])
 def test_unsafe_metadata_no_key_read_no_marker(self):
  from types import SimpleNamespace
  scope=self.scope();node=lambda mode,uid=10317,gid=1002,nlink=1:SimpleNamespace(st_mode=mode,st_uid=uid,st_gid=gid,st_nlink=nlink)
  class OS:
   O_RDONLY=0;O_DIRECTORY=1;O_NOFOLLOW=2;R_OK=4
   def getuid(self):return 10317
   geteuid=getuid
   def getgid(self):return 1003
   getegid=getgid
   def access(self,*args,**kwargs):return True
   def open(self,*args,**kwargs):return 1
   def close(self,fd):pass
   def fstat(self,fd):return node(stat.S_IFDIR|0o755,0,0,2)
   def stat(self,path,**kwargs):return node(stat.S_IFREG|0o644) if path=='openai_config.php' else node(stat.S_IFDIR|0o755,0,0,2)
  scope['os']=OS();scope['reserve_ai']=Mock();scope['subprocess']=Mock()
  result=scope['dogado_pilot'](self.data())
  self.assertEqual(result['error_code'],'CONFIG_MODE');self.assertEqual(result['config_metadata']['file']['mode'],0o644)
  self.assertIn('GID',result['config_metadata']['legacy_deviations']);self.assertEqual(result['model_calls'],0)
  scope['subprocess'].run.assert_not_called();scope['reserve_ai'].assert_not_called()
