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
  s=snapshot();s['current_observation_ids']=[f['observation_id'] for f in s['facts'] if f['end']=='2025-12-31'];return dict(snapshot=s,price=PRICE,invocation_id='synthetic-dogado',modules={n:Path('scripts/fundamentals/'+n+'.py').read_text() for n in ('assessment','responses_transport')},marker=dict(execution='fundamentals-ai-droneshield-existing-mosa-20261101-01',commit='a'*40,isin='AU000000DRO2',model='gpt-6.1-sol',input_digest=prepare(s)[1],workflow='.github/workflows/fundamentals-assessment-existing-mosa-once.yml'))
 def test_server_side_validated_success_key_never_returned(self):
  scope=self.scope();data=self.data();events=[]
  scope['existing_key']=lambda *args:dict(key='synthetic-local-key',hash='synthetic-config-hash',identity=dict(mode=0o644))
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
  self.assertEqual(r['input_digest_verified'],'PASS');self.assertEqual(r['reasoning'],'medium')
  self.assertEqual(r['interpretation_details'][0]['code'],'CURATED_ROUNDING')
  self.assertNotIn('value',r['interpretation_details'][0])
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
  code=Path('.github/workflows/fundamentals-assessment-existing-mosa-once.yml').read_text()
  self.assertNotIn('MOSA2_OPENAI_API_KEY',code);self.assertIn('github.run_number == 1',code)
  self.assertIn('github.run_attempt == 1',code);self.assertIn('MOSA2-DRONESHIELD-EXISTING-MOSA-AI-ONCE-20261101:',code)

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

 def test_644_exception_exact_path_owner_group_python_php_parity(self):
  import subprocess
  scope=self.scope();base=dict(type=stat.S_IFREG,uid=10317,gid=1003,mode=0o644,symlink=False,nlink=1)
  cases=[(base,scope['CONFIG']),(base,scope['CONFIG']+'.other'),(base,None),
    (dict(base,uid=999),scope['CONFIG']),(dict(base,gid=1002),scope['CONFIG']),
    (dict(base,symlink=True),scope['CONFIG']),(dict(base,nlink=2),scope['CONFIG']),
    (dict(base,mode=0o664),scope['CONFIG'])]
  expected=[scope['file_policy'](m,10317,1003,p) for m,p in cases]
  self.assertEqual(expected[0],'PASS');self.assertTrue(all(x!='PASS' for x in expected[1:]))
  code=scope['PHP_POLICY']+"$rows=json_decode(stream_get_contents(STDIN),true);echo json_encode(array_map(fn($r)=>filePolicy($r[0],10317,1003,$r[1]),$rows));"
  r=subprocess.run(['php','-n','-r',code],input=json.dumps(cases),capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout),expected)

 def test_exact_644_metadata_stability_and_concrete_other_access_stop(self):
  from types import SimpleNamespace
  scope=self.scope()
  def node(mode,ino=1):
   return SimpleNamespace(st_mode=mode,st_uid=10317,st_gid=1003,st_nlink=1,st_dev=1,st_ino=ino,st_size=100,st_mtime_ns=10,st_ctime_ns=20)
  class OS:
   O_RDONLY=0;O_DIRECTORY=1;O_NOFOLLOW=2;R_OK=4
   world=False;changed=False
   def getuid(self):return 10317
   geteuid=getuid
   def getgid(self):return 1003
   getegid=getgid
   def access(self,*args,**kwargs):return True
   def open(self,p,*args,**kwargs):return 2 if p=='openai_config.php' else 1
   def close(self,fd):pass
   def fstat(self,fd):return node(stat.S_IFREG|0o644,2 if self.changed else 1) if fd==2 else node(stat.S_IFDIR|0o755)
   def stat(self,p,**kwargs):return node(stat.S_IFREG|0o644) if p=='openai_config.php' else node(stat.S_IFDIR|(0o755 if self.world else 0o710))
  fake=OS();scope['os']=fake
  report={};scope['protection_diagnosis'](report)
  self.assertEqual(report['protection_policy'],'PASS');self.assertEqual(report['security_risk'],'LOCAL_READ_ISOLATION_UNPROVEN')
  fake.changed=True
  with self.assertRaisesRegex(RuntimeError,'^CONFIG_CHANGED$'):scope['protection_diagnosis']({})
  fake.changed=False;fake.world=True;scope['subprocess']=Mock();scope['reserve_ai']=Mock()
  r=scope['dogado_pilot'](self.data())
  self.assertEqual(r['error_code'],'CONFIG_OTHER_READ_ACCESS');self.assertEqual(r['model_calls'],0)
  scope['subprocess'].run.assert_not_called();scope['reserve_ai'].assert_not_called()
