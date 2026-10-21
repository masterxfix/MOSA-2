"""Harmless standard-library, interpreter and child-process capability probe."""
import importlib
import json
import os
import sys

MODULES = ('argparse','ast','base64','copy','dataclasses','datetime','decimal','fractions','hashlib',
           'importlib.util','json','math','pathlib','re','subprocess','types','typing',
           'urllib.request','urllib.parse','urllib.error','ssl','resource','signal','time')
report = dict(ok=False, python_version=sys.version.split()[0], executable=sys.executable,
              version_info=list(sys.version_info[:3]), modules={}, provider_requests=0, database_connections=0)
for name in MODULES:
    try:
        importlib.import_module(name)
        report['modules'][name] = 'PASS'
    except Exception:
        report['modules'][name] = 'FAIL'
try:
    scope = {}
    exec(compile('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass C:\n    v: str | None\n    pairs: tuple[tuple[str, str], ...]\n', '<mosa-readiness-syntax>', 'exec'), scope)
    report['collector_syntax'] = 'PASS'
except Exception:
    report['collector_syntax'] = 'FAIL'
try:
    import resource
    limits = {}
    for name in ('RLIMIT_CPU','RLIMIT_AS','RLIMIT_DATA','RLIMIT_RSS','RLIMIT_STACK','RLIMIT_NPROC','RLIMIT_NOFILE','RLIMIT_FSIZE'):
        if hasattr(resource,name):
            soft,hard=resource.getrlimit(getattr(resource,name))
            limits[name]=dict(soft=soft,hard=hard)
    report['process_limits']=limits
except Exception:
    report['process_limits']='UNAVAILABLE'
try:
    import ssl
    context=ssl.create_default_context()
    report['tls']=dict(openssl=ssl.OPENSSL_VERSION,sni=ssl.HAS_SNI,ca_certificates=context.cert_store_stats()['x509_ca'])
except Exception:
    report['tls']=dict(failure='TLS_CONTEXT_UNAVAILABLE')
try:
    import subprocess
    data=json.loads(sys.stdin.read())
    php=data['php_binary']
    flags=data['php_flags']
    public_php='echo json_encode(array("version"=>PHP_VERSION,"version_id"=>PHP_VERSION_ID,"binary"=>PHP_BINARY,"pdo_mysql"=>class_exists("PDO")&&in_array("mysql",PDO::getAvailableDrivers(),true)));'
    env={'PATH':os.environ.get('PATH',''),'PYTHONDONTWRITEBYTECODE':'1'}
    report['python_to_php']={}
    for mode in ('existing_path','pinned_path'):
        child_env=dict(env)
        if mode=='pinned_path':
            child_env['PATH']=os.path.dirname(php)+os.pathsep+env['PATH']
        try:
            child=subprocess.run(['php']+flags+['-r',public_php],stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=3,env=child_env)
            result=json.loads(child.stdout.decode('utf-8')) if child.returncode==0 and not child.stderr else None
            report['python_to_php'][mode]=dict(ok=bool(result and 80400<=result['version_id']<80500 and result['pdo_mysql']),runtime=result)
        except Exception:
            report['python_to_php'][mode]=dict(ok=False,failure='PHP_CHILD_UNAVAILABLE')
    import signal
    import time
    child=None
    try:
        child=subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(2)'],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env,start_new_session=True)
        group=os.getpgid(child.pid)
        if group!=child.pid or group==os.getpgrp():
            raise RuntimeError('group ownership')
        os.killpg(group,signal.SIGTERM)
        child.wait(timeout=2)
        report['own_process_group_termination']='PASS'
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=2)
except Exception:
    report['process_test_failure']='CHILD_PROCESS_CHECK_FAILED'
report['provider_tls_primitives']=bool(report.get('tls',{}).get('sni') and report.get('tls',{}).get('ca_certificates',0)>0)
report['typing_protocol']=hasattr(importlib.import_module('typing'),'Protocol')
report['minimum_version']='PASS' if sys.version_info>=(3,10) else 'FAIL'
report['ok']=(report['minimum_version']=='PASS' and report['collector_syntax']=='PASS'
    and all(v=='PASS' for v in report['modules'].values())
    and report.get('python_to_php',{}).get('pinned_path',{}).get('ok',False)
    and report.get('own_process_group_termination')=='PASS'
    and report['provider_tls_primitives'] and report['typing_protocol'])
print(json.dumps(report,sort_keys=True))
