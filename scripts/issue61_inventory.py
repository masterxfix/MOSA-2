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
def process_inventory():
    try:
        p=subprocess.run(['ps','-u',str(os.getuid()),'-o','pid=','-o','ppid=','-o','args='],
                         capture_output=True,text=True,timeout=6)
        if p.returncode:
            return {'visible':False,'exit':p.returncode}
        excluded={os.getpid(),os.getppid()}
        matches=inspected=0
        for line in p.stdout.splitlines():
            if not line.strip():
                continue
            parts=line.split(None,2)
            if len(parts)<2 or not all(part.isdigit() for part in parts[:2]):
                return {'visible':False}
            pid,ppid=map(int,parts[:2])
            inspected+=1
            if pid not in excluded and ppid!=os.getpid() and len(parts)==3 and writer.search(parts[2]):
                matches+=1
        return {'visible':inspected>0,'matches':matches}
    except (OSError,subprocess.TimeoutExpired):
        return {'visible':False}
def unit_inventory(roots):
    found=matched=0
    for root in roots:
        try:
            with os.scandir(root) as entries:
                for item in entries:
                    if not item.name.endswith(('.timer','.service')):
                        continue
                    if item.is_symlink() and os.path.realpath(item.path)=='/dev/null':
                        continue
                    with open(item.path,'r',encoding='utf-8',errors='replace') as stream:
                        text=stream.read(65537)
                    if len(text)>65536:
                        return {'visible':False}
                    matched+=bool(markers.search(item.name+'\n'+text))
            found+=1
        except FileNotFoundError:
            continue
        except OSError:
            return {'visible':False}
    return {'visible':bool(found),'roots_found':found,'matches':matched}
print(json.dumps({
    'cron':run(['crontab','-l'],markers,True),
    'user_timers':run(['systemctl','--user','list-timers','--all','--no-legend','--no-pager'],markers),
    'system_timers':run(['systemctl','list-timers','--all','--no-legend','--no-pager'],markers),
    'system_unit_files':unit_inventory(['/etc/systemd/system','/run/systemd/system','/usr/lib/systemd/system','/lib/systemd/system']),
    'user_unit_files':unit_inventory([os.path.expanduser('~/.config/systemd/user'),'/etc/systemd/user','/usr/lib/systemd/user']),
    'user_processes':process_inventory(),
    'private_storage':private_directory('/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector'),
}))
"""


WEB_READER = r"""
try {
    $root='/var/www/vhosts/web213.server10.configcenter.info/mosa2-market-read-private/access.php';
    if (realpath($root)!==$root || !is_file($root) || (fileperms($root)&0077)!==0) throw new RuntimeException();
    $c=require $root;
    $dsn='mysql:host=127.0.0.1;port=3307;dbname=h29077_mosa2_test;charset=utf8mb4';
    $u='h29077_mosa2_read';
    if ($c['dsn']!==$dsn || $c['user']!==$u) throw new RuntimeException();
    $db=new PDO($dsn,$u,$c['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_TIMEOUT=>4]);
    unset($c);
    if ($db->query('SELECT DATABASE()')->fetchColumn()!=='h29077_mosa2_test' ||
        $db->query('SELECT CURRENT_USER()')->fetchColumn()!==$u.'@localhost' ||
        $db->query('SELECT CURRENT_ROLE()')->fetchColumn()!=='NONE') throw new RuntimeException();
    $db->exec('SET SESSION TRANSACTION READ ONLY');
    if (!$db->beginTransaction()) throw new RuntimeException();
    $schema='h29077\\_mosa2\\_test';
    $host='`'.$u.'`@`localhost`';
    $grants=$db->query('SHOW GRANTS FOR CURRENT_USER')->fetchAll(PDO::FETCH_COLUMN);
    $select=false;
    foreach ($grants as $grant) {
        if ($grant==='GRANT USAGE ON *.* TO '.$host) continue;
        $matched=false;
        foreach (['SELECT','SELECT, SHOW VIEW'] as $rights) {
            if ($grant==='GRANT '.$rights.' ON `'.$schema.'`.* TO '.$host) $matched=true;
        }
        if (!$matched) throw new RuntimeException();
        $select=true;
    }
    if (!$select || !$db->rollBack()) throw new RuntimeException();
    echo '{"configured_db_account_select_only":true}';
} catch (Throwable) {
    echo '{"configured_db_account_select_only":false}';
}
"""


def database(port, env):
    child_env = {key:env[key] for key in ('PATH','HOME','LANG') if key in env}
    reply = subprocess.run(['php', str(Path(__file__).with_suffix('.php'))],
                           input=json.dumps(dict(port=port,password=env['MOSA_TEST_DB_PASSWORD'])),
                           text=True, capture_output=True, timeout=240, env=child_env)
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
            binary, _ = remote.capability(transport)
            rc, data, errors, _ = remote.remote_call(transport,remote.command(binary,WEB_READER),timeout=22)
            result['web_reader'] = json.loads(data) if rc==0 and not errors else {'configured_db_account_select_only':False}
            with access.tunnel(transport,result) as port:
                result['database'] = database(port,env)
                result['ok'] = result['database'].get('ok') is True and 'cron' in result['subscription']
    except subprocess.TimeoutExpired:
        result['failure']='DB_INVENTORY_DEADLINE_EXCEEDED'
    except Exception:
        result['failure']='INVENTORY_TRANSPORT_REJECTED'
    return result


if __name__=='__main__':
    result=execute(os.environ)
    text=access.public_text(result,os.environ)
    print(text)
    sys.exit(0 if result['ok'] and json.loads(text).get('ok') else 1)
