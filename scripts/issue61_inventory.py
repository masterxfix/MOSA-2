"""Read-only subscription and Schema 6 evidence for the authorized M2 reset."""
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys

import collector_actions as access
import collector_db_locality as remote

HOST_INVENTORY = r"""
import json, os, re, stat, subprocess
markers = re.compile(r'mosa[ ._-]?2|h29077_mosa2_test|collector_scheduler\.php', re.I)
writer = re.compile(r'collector_scheduler|collector_cycle|collector_runtime|history_queue|fundamentals.*import|database_reset|market_collector', re.I)
def run(argv, classifier, allow_missing=False):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=6)
        if p.returncode == 0:
            return {'visible':True, 'matches':sum(bool(classifier.search(s)) for s in p.stdout.splitlines())}
        if allow_missing and p.returncode == 1 and 'no crontab for' in p.stderr.lower():
            return {'visible':True, 'matches':0}
        return {'visible':False,'exit':p.returncode}
    except (OSError, subprocess.TimeoutExpired):
        return {'visible':False,'exit':None}
def private_directory(path):
    try:
        s=os.lstat(path)
        return stat.S_ISDIR(s.st_mode) and stat.S_IMODE(s.st_mode)==0o700 and s.st_uid==os.getuid()
    except OSError:
        return False
print(json.dumps({
    'cron':run(['crontab','-l'],markers,True),
    'user_timers':run(['systemctl','--user','list-timers','--all','--no-legend','--no-pager'],markers),
    'system_timers':run(['systemctl','list-timers','--all','--no-legend','--no-pager'],markers),
    'user_processes':run(['ps','-u',str(os.getuid()),'-o','args='],writer),
    'private_storage':private_directory('/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector'),
}))
"""


def database(port, env):
    child_env = {key:env[key] for key in ('PATH','HOME','LANG') if key in env}
    reply = subprocess.run(['php', str(Path(__file__).with_suffix('.php'))],
                           input=json.dumps(dict(port=port,password=env['MOSA_TEST_DB_PASSWORD'])),
                           text=True, capture_output=True, timeout=90, env=child_env)
    if reply.stderr or len(reply.stdout)>30000:
        raise RuntimeError('DB_INVENTORY_OUTPUT_REJECTED')
    return json.loads(reply.stdout)


def execute(env):
    import paramiko
    logging.getLogger('paramiko').disabled = True
    result = {'ok':False,'provider_requests':0,'database_writes':0}
    try:
        with access.ssh_client(access.configuration(env), result, paramiko) as transport:
            cmd = shlex.join(['/opt/alt/python311/bin/python3.11','-I','-B','-c',HOST_INVENTORY])
            rc, data, errors, _ = remote.remote_call(transport,cmd,timeout=35)
            if rc==0 and not errors:
                result['subscription'] = json.loads(data)
            else:
                result['subscription'] = {'ok':False,'reason':'SUBSCRIPTION_INVENTORY_FAILED'}
            with access.tunnel(transport,result) as port:
                result['database'] = database(port,env)
                result['ok'] = result['database'].get('ok') is True and 'cron' in result['subscription']
    except Exception:
        result['failure']='INVENTORY_TRANSPORT_REJECTED'
    return result


if __name__=='__main__':
    result=execute(os.environ)
    text=access.public_text(result,os.environ)
    print(text)
    sys.exit(0 if result['ok'] and json.loads(text).get('ok') else 1)
