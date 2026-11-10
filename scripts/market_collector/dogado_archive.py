"""Private Dogado execution of the existing commit-bound market batch."""
import base64
import hashlib
import json
import logging
import os
from pathlib import Path
import shlex

import collector_db_locality as remote
import collector_private_directories as directories

EXTRA_FILES = ('api/market_core/native_currency_units.json', 'scripts/market_collector/gettex_delayed.py')
SUPERVISOR = r"""
import base64
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess

def run_archive(data):
    scope=data['scope']
    archive=scope['archive']
    need(scope['mode']=='manual' and scope['source_priority']==['provider:gettex_mund_delayed']
         and scope['request_budget']==1 and len(scope['expected_isins'])==1, 'ARCHIVE_SCOPE')
    need(os.getuid()==UID and os.getgid()==GID,'ARCHIVE_OWNER')
    root=BASE+'/private/mosa2-collector/runs'
    web=BASE+'/mosa2-test.scharwerk.de'
    need(not inside(root,web),'ARCHIVE_PUBLIC_ROOT')
    parent=checked_fd(os,root,base_identity=None)
    try:
        identity=scope['expected_isins'][0]+':'+archive['slot']
        name='gettex-'+hashlib.sha256(identity.encode()).hexdigest()
        os.umask(0o077)
        os.mkdir(name,0o700,dir_fd=parent)
        work=Path(root)/name
        need(work.resolve()==work,'ARCHIVE_WORK_PATH')
    finally:
        os.close(parent)
    project=work/'release'
    project.mkdir(mode=0o700)
    total=0
    for name, entry in data['files'].items():
        path=PurePosixPath(name)
        need(not path.is_absolute() and path.as_posix()==name and
             all(re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]*',part) and part not in ('.','..') for part in path.parts),
             'ARCHIVE_PACKAGE_PATH')
        raw=base64.b64decode(entry['bytes'],validate=True)
        total+=len(raw)
        need(total<=4*1024*1024 and hashlib.sha256(raw).hexdigest()==entry['sha256'],'ARCHIVE_PACKAGE_DIGEST')
        target=project/path
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with target.open('xb') as out:
            out.write(raw)
        need(hashlib.sha256(target.read_bytes()).hexdigest()==entry['sha256'],'ARCHIVE_PACKAGE_READBACK')
    runs=work/'batch'
    runs.mkdir(mode=0o700)
    php='/opt/plesk/php/8.4/bin/php'
    python='/opt/alt/python311/bin/python3.11'
    path='/opt/plesk/php/8.4/bin:/usr/bin:/bin'
    config=dict(python=python,php=php,project=str(project),runtime_path=path,public_root=web,
                db_host='127.0.0.1',db_port=3307,private_dogado=True,
                state_contract=dict(schema_version=6,allow_current=True))
    child=subprocess.run([php,'-d','display_errors=0','-d','log_errors=0',
                           str(project/'scripts/market_collector/live_batch.php')],
        input=json.dumps(dict(config=config,password=data['password'],scope=scope,private_root=str(runs))).encode(),
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=project,
        env={'PATH':path,'LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'},timeout=180)
    need(not child.stderr and len(child.stdout)<=1048576,'ARCHIVE_BATCH_RESULT')
    result=json.loads(child.stdout)
    batch=result.get('batch') or {}
    current=result.get('current') or {}
    items=batch.get('item_results',[])
    allowed={'qualification','batch','current','readback','complete'}
    failure=result.get('failure')
    code=failure if isinstance(failure,str) and re.fullmatch('[a-z0-9_]{1,90}',failure) else None
    return dict(ok=child.returncode==0 and result.get('ok') is True, stage=result.get('stage') if result.get('stage') in allowed else 'preflight',
                failure=code, provider_requests=result.get('provider_requests'), database_writes=result.get('database_writes'), route_writes=result.get('route_writes'),
                observation=(items[0].get('writer') if len(items)==1 else None),
                observation_readback=(items[0].get('readback') if len(items)==1 else None),
                current_readback=current.get('readback'), current_decisions=current.get('decisions'), protection=result.get('protection'))

try:
    request=json.loads(sys.stdin.buffer.read(6000001))
    print(json.dumps(run_archive(request)))
except FileExistsError:
    print(json.dumps(dict(ok=False,stage='reservation',failure='ARCHIVE_ALREADY_CONSUMED')))
except Stop as error:
    print(json.dumps(dict(ok=False,stage='dogado',failure=str(error))))
except Exception as error:
    print(json.dumps(dict(ok=False,stage='dogado',failure=type(error).__name__)))
"""

def execute(transport, project, scope, password):
    from scripts import collector_release as release
    from scripts.market_collector import gettex_delayed
    from datetime import datetime, timezone

    now=datetime.now(timezone.utc).strftime(gettex_delayed.STAMP)
    gettex_delayed.GettexDelayedTradeV1().archive_request(scope['expected_isins'][0],now,scope['archive']['slot'])
    commit=release.git(project,'rev-parse','HEAD').decode().strip()
    _,read=release.repository(project,commit)
    contract=release.decode(read(release.SCHEMA6_CONTRACT))
    paths={row['path'] for row in contract['files']}|set(EXTRA_FILES)
    files={}
    for name in sorted(paths):
        raw=read(name)
        files[name]=dict(bytes=base64.b64encode(raw).decode('ascii'),sha256=hashlib.sha256(raw).hexdigest())
    common=directories.REMOTE_SOURCE.split('if __name__=="__main__":')[0]
    command=shlex.join([directories.PYTHON,'-I','-B','-c',common+'\n'+SUPERVISOR])
    payload=json.dumps(dict(files=files,scope=scope,password=password),separators=(',',':')).encode()
    logging.getLogger('paramiko').disabled=True
    code,out,errors,_=remote.remote_call(transport,command,payload,timeout=240)
    if code or errors:
        raise remote.ProbeError('ARCHIVE_REMOTE_RESULT_UNKNOWN')
    return json.loads(out)
