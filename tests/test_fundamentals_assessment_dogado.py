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
  s=snapshot();s['current_observation_ids']=[f['observation_id'] for f in s['facts'] if f['end']=='2025-12-31'];return dict(snapshot=s,price=PRICE,invocation_id='synthetic-dogado',modules={n:Path('scripts/fundamentals/'+n+'.py').read_text() for n in ('assessment','responses_transport')},marker=dict(execution='fundamentals-ai-droneshield-existing-mosa-20261101-02',commit='a'*40,isin='AU000000DRO2',model='gpt-6.1-sol',input_digest=prepare(s)[1],workflow='.github/workflows/fundamentals-assessment-existing-mosa-once.yml'))
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
     events.append('post');rules=json.loads(request['input'])['interpretation_contract']
     def all_codes(output):
      output['interpretations']=[dict(code=code,observation_ids=rule['observation_ids'],calculation_ids=rule['calculation_ids']) for code,rule in rules.items() if rule['enabled']]
      return output
     return response(request,all_codes)
   t.OpenAIResponsesTransport=Fake;return a,t
  scope['load_modules']=modules
  r=scope['dogado_pilot'](data)
  self.assertTrue(r['ok'],r);self.assertEqual(events,['marker','post']);self.assertEqual(r['model_calls'],1)
  self.assertFalse(r['key_transferred']);self.assertNotIn('synthetic-local-key',json.dumps(r));self.assertNotIn('factual_claims',r)
  self.assertEqual(r['input_digest_verified'],'PASS');self.assertEqual(r['reasoning'],'medium')
  self.assertIn('CURATED_ROUNDING',[v['code'] for v in r['interpretation_details']])
  self.assertNotIn('value',r['interpretation_details'][0])
  self.assertEqual(r['configuration_readback'],'PASS');self.assertTrue(r['mosa_unchanged'])
  self.assertEqual(len(r['financial_evidence']['facts']),14)
  self.assertLess(len(json.dumps(r,separators=(',',':')).encode())+2200,8192) # wire format plus protection metadata
 def test_missing_exact_config_stops_before_marker_or_post(self):
  scope=self.scope();scope['existing_key']=Mock(side_effect=RuntimeError('CONFIG_NOT_VISIBLE_OR_READABLE'));scope['reserve_ai']=Mock()
  r=scope['dogado_pilot'](self.data());self.assertFalse(r['ok']);self.assertEqual(r['error_code'],'CONFIG_NOT_VISIBLE_OR_READABLE');self.assertEqual(r['model_calls'],0);scope['reserve_ai'].assert_not_called()
 def test_interpretation_failure_reports_only_safe_code_and_reason(self):
  scope=self.scope();data=self.data();events=[]
  scope['existing_key']=lambda *args:dict(key='synthetic-local-key',hash='synthetic-config-hash',identity={})
  scope['reserve_ai']=lambda marker:events.append('marker');real_loader=scope['load_modules']
  def modules(bundle):
   a,t=real_loader(bundle)
   class Fake:
    def __init__(self,*args,**kwargs):pass
    def __call__(self,req,**kwargs):
     events.append('post');p=json.loads(req['input'])['snapshot']
     ref=next(c['calculation_id'] for c in p['calculations'] if c['kind']=='margin_percent')
     def invalid(output):
      output['interpretations']=[dict(code='NUMERICAL_INCREASE',observation_ids=[],calculation_ids=[ref])];return output
     return response(req,invalid)
   t.OpenAIResponsesTransport=Fake;return a,t
  scope['load_modules']=modules;r=scope['dogado_pilot'](data)
  self.assertFalse(r['ok']);self.assertEqual(events,['marker','post'])
  self.assertEqual(r['error_code'],'INTERPRETATION_BINDING:NUMERICAL_INCREASE:WRONG_CALCULATION_KIND')
  self.assertEqual(r['cost_status'],'ESTIMATE_UNVALIDATED_RESPONSE')
  self.assertEqual(r['actual_cost_upper_bound_usd'],'0.002475')
  self.assertEqual(r['configuration_readback'],'PASS');self.assertTrue(r['mosa_unchanged'])
  self.assertNotIn('synthetic-local-key',json.dumps(r));self.assertNotIn('calculation_ids',json.dumps(r));self.assertNotIn('factual_claims',r)
 def test_config_permission_and_php_failure_are_safe(self):
  scope=self.scope()
  scope['protection_diagnosis']=Mock(side_effect=PermissionError('private path not to publish'))
  with self.assertRaisesRegex(RuntimeError,'^CONFIG_NOT_VISIBLE_OR_READABLE$'):scope['existing_key']()
  self.assertEqual(scope['CONFIG'],'/var/www/vhosts/web213.server10.configcenter.info/httpdocs/scharwerk.de/dashboard_neu/data/private/openai_config.php')
  code=Path('scripts/fundamentals/assessment_dogado_remote.py').read_text();self.assertNotIn('listdir',code);self.assertNotIn('glob(',code)
 def test_fileless_package_and_workflow_without_api_secret(self):
  scope=self.scope();a,t=scope['load_modules'](self.data()['modules']);self.assertEqual(a.DEFAULTS['model'],'gpt-6.1-sol')
  code=Path('.github/workflows/fundamentals-assessment-existing-mosa-once.yml').read_text()
  self.assertNotIn('MOSA2_OPENAI_API_KEY',code);self.assertIn('github.run_number == 2',code)
  self.assertIn('github.run_attempt == 1',code);self.assertIn('MOSA2-DRONESHIELD-SECOND-AI-20261101:',code)
  self.assertIn('test "$GITHUB_RUN_NUMBER" = "2"',code)

 def test_second_run_guard_rejects_other_runs_attempts_and_authorizations(self):
  from scripts import fundamentals_assessment_dogado_once as runner
  sha='a'*40
  env=dict(GITHUB_REPOSITORY='masterxfix/MOSA-2',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER='2',GITHUB_SHA=sha,EXPECTED_COMMIT=sha,AUTHORIZATION='MOSA2-DRONESHIELD-SECOND-AI-20261101:'+sha,GITHUB_WORKFLOW_REF='masterxfix/MOSA-2/'+runner.WORKFLOW+'@refs/heads/main')
  for changed,allowed in [({},True),({'GITHUB_RUN_NUMBER':'1'},False),({'GITHUB_RUN_NUMBER':'3'},False),({'GITHUB_RUN_ATTEMPT':'2'},False),({'EXPECTED_COMMIT':'b'*40},False),({'AUTHORIZATION':'old'},False)]:
   with self.subTest(changed=changed),patch.object(runner.shared,'no_other_runs') as runs,patch.object(runner.shared.access,'configuration',side_effect=RuntimeError('synthetic stop before network')) as access:
    r=runner.execute(dict(env,**changed));self.assertEqual(r['model_calls'],0)
    self.assertEqual(runs.call_count,int(allowed));self.assertEqual(access.call_count,int(allowed))

 def test_final_db_readback_preserves_first_model_failure_and_unknown_outcome(self):
  from contextlib import nullcontext
  from scripts import fundamentals_assessment_dogado_once as runner
  s=self.data()['snapshot'];error='INTERPRETATION_BINDING:NUMERICAL_INCREASE:WRONG_SIGN'
  for remote,readback,expected in [(dict(ok=False,model_calls=1,error_code=error,stage='MODEL_POST_AND_VALIDATION'),s,error),
     (dict(ok=False,model_calls=1,error_code=error,stage='MODEL_POST_AND_VALIDATION'),RuntimeError('private DB error'),error),
     (RuntimeError('unknown remote result'),s,'RUNNER_STOP_NO_RETRY')]:
   with patch.object(runner.shared,'guard'),patch.object(runner.shared,'no_other_runs'),patch.object(runner.shared.access,'configuration'),patch.object(runner.shared.access,'ssh_client',return_value=nullcontext(object())),patch.object(runner.shared.access,'tunnel',return_value=nullcontext(3307)),patch.object(runner,'read_db',side_effect=[s,readback]) as reads,patch.object(runner,'remote_pilot',side_effect=remote if isinstance(remote,Exception) else None,return_value=remote):
    r=runner.execute(dict(GITHUB_RUN_NUMBER='2',GITHUB_WORKFLOW_REF='masterxfix/MOSA-2/'+runner.WORKFLOW+'@refs/heads/main'))
   self.assertFalse(r['ok']);self.assertEqual(r['error_code'],expected);self.assertEqual(reads.call_count,2)
   self.assertEqual(r['db_unchanged'],not isinstance(readback,Exception))
   self.assertEqual(r['model_calls'],'UNKNOWN_NO_RETRY' if isinstance(remote,Exception) else 1)

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
