"""Read-only investigation of the existing failed PNE run. Never starts the collector."""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shlex
import stat
import sys
from scripts import collector_dogado_pne as live
import collector_actions as shared
import collector_db_locality as remote

PROBE = r'''
import json,os,resource,subprocess,sys
d=json.loads(sys.stdin.read(100001))
assert set(d)=={"source","release"}
assert d["release"]=="/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector/releases/92274a79550b8acd719434459022da6de5261d2e"
php="/opt/plesk/php/8.4/bin/php"
flags=["-d","display_errors=0","-d","log_errors=0","-d","opcache.enable_cli=0","-d","opcache.file_cache=","-d","memory_limit=128M"]
env=dict(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin",PYTHONDONTWRITEBYTECODE="1")
def limits(m):
    def apply():
        resource.setrlimit(resource.RLIMIT_AS,(m*1024*1024,m*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(10,10))
        resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    return apply
def classify(r):
    e=r.stderr.lower()
    if b"failed to map segment" in e or b"cannot allocate memory" in e or b"out of memory" in e or b"mmap" in e:return "PHP_ADDRESS_SPACE_EXHAUSTED"
    if b"parse error" in e or b"syntax error" in e:return "PHP_SYNTAX_ERROR"
    if b"permission denied" in e:return "PHP_START_PERMISSION"
    return "PHP_STDERR" if e else ("PHP_NONZERO_EXIT" if r.returncode else "NONE")
rows=[]
# Two bounded cases in ONE harmless test: historical limit and candidate correction.
# Source includes libraries and emits a fixed startup receipt only; no main()/perform().
for mib in (256,1024):
    p=subprocess.run([php,*flags,"-r",d["source"]],input=b"",stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        cwd=d["release"],env=env,preexec_fn=limits(mib),timeout=15)
    assert len(p.stdout)+len(p.stderr)<=65536
    row=dict(address_space_mib=mib,php_process_started=True,php_exitcode=p.returncode,
             failure_code=classify(p),stderr_suppressed=bool(p.stderr),provider_started=False,
             database_connections=0,collector_calls=0)
    if p.returncode==0 and not p.stderr:
        receipt=json.loads(p.stdout)
        assert receipt==dict(startup="PASS",php="8.4.12",pdo_mysql=True)
        row["startup"]="PASS"
    else:row["startup"]="FAIL"
    rows.append(row)
print(json.dumps(dict(cases=rows,remote_files_written=0,provider_requests=0,database_connections=0)))
'''

DB = r'''
require_once '@RELEASE@/scripts/phase2/postcheck.php';
use function Mosa2\Phase2\{connection,check,qi};
try {
    $input=json_decode(stream_get_contents(STDIN),true,8,JSON_THROW_ON_ERROR);
    $p=connection($input['password']);unset($input);
    $p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
    try {
        $q=$p->prepare("SELECT asset_id FROM m2_asset_identifiers WHERE identifier_type='isin' AND normalized_value=? AND scope_key='' LIMIT 2");
        $q->execute(['DE000A0JBPG2']);$ids=$q->fetchAll();check(count($ids)===1,'pne_identity');
        $asset=(string)$ids[0]['asset_id'];$tables=[];
        foreach(['m2_market_observations','m2_market_current','m2_market_bars'] as $table){
            $cols=$p->query('SHOW COLUMNS FROM '.qi($table))->fetchAll();$select=[];
            foreach($cols as $c)$select[]=(str_starts_with(strtolower($c['Type']),'binary(')?'HEX('.qi($c['Field']).')':qi($c['Field'])).' AS '.qi($c['Field']);
            $keys=$p->query('SHOW KEYS FROM '.qi($table)." WHERE Key_name='PRIMARY'")->fetchAll();
            check($keys!==[],'primary_key');
            $all=$p->query('SELECT '.implode(',',$select).' FROM '.qi($table).' ORDER BY '.implode(',',array_map(static fn($k)=>qi($k['Column_name']),$keys)).' LIMIT 1001')->fetchAll();
            check(count($all)<=1000,'bounded_state');
            $pne=array_values(array_filter($all,static fn($r)=>(string)$r['asset_id']===$asset));
            $idsOut=[];foreach($pne as $r)$idsOut[]=array_intersect_key($r,array_flip(['id','created_at','observed_at','market_at']));
            $tables[$table]=['total_rows'=>count($all),'pne_rows'=>count($pne),'pne_ids'=>$idsOut,
                'sha256'=>hash('sha256',json_encode($all,JSON_THROW_ON_ERROR))];
        }
        $r=['ok'=>true,'identity'=>'PASS','read_only'=>true,'asset_id'=>$asset,'tables'=>$tables,
            'business_writes'=>0,'provider_requests'=>0,'historical_equality'=>'UNBESTAETIGT'];
    }finally{if($p->inTransaction())$p->rollBack();}
    $p=null;echo json_encode($r,JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['ok'=>false,'failure_code'=>'READ_ONLY_DB_CHECK_FAILED']);}
'''

def fingerprint(sftp):
    """Existing single run only, no contents from other runs. No writable handle."""
    path=live.RUN
    root=sftp.lstat(path)
    if (stat.S_IFMT(root.st_mode),root.st_uid,root.st_gid,stat.S_IMODE(root.st_mode))!=(stat.S_IFDIR,10317,1003,0o700):
        raise ValueError("RUN_METADATA")
    if sftp.normalize(path)!=path:raise ValueError("RUN_CANONICAL")
    names=sftp.listdir(path)
    permitted={"job.lock","started.json","result.json","live-manifest.json","provider-consumed.lock"}
    if not set(names)<=permitted:raise ValueError("UNEXPECTED_RUN_OBJECT")
    rows={};public={}
    for name in sorted(names):
        p=path+"/"+name;s=sftp.lstat(p)
        if (stat.S_IFMT(s.st_mode),s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))!=(stat.S_IFREG,10317,1003,0o600) or s.st_size>65536:
            raise ValueError("RUN_FILE_METADATA")
        with sftp.open(p,"rb") as f:raw=f.read(65537)
        if len(raw)!=s.st_size:raise ValueError("RUN_FILE_SIZE")
        rows[name]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),mtime=s.st_mtime)
        if name in ("started.json","result.json"):
            obj=json.loads(raw)
            # Copy only fixed safe historical values, never arbitrary strings.
            public[name]=dict(commit_matches=obj.get("commit")=="307c718fdd326c51188f3e1f05f0eb7d75ab72a2")
            if name=="result.json":
                public[name].update(status_unknown=obj.get("status")=="OUTCOME_UNKNOWN",
                    failure_type_stop=obj.get("failure_type")=="Stop",provider_requests_zero=obj.get("provider_requests")==0)
    return dict(files=rows,summary=public,provider_marker="PRESENT" if "provider-consumed.lock" in names else "ABSENT",
                live_manifest="PRESENT" if "live-manifest.json" in names else "ABSENT")

def startup_source(release_root=live.RELEASE):
    code=live.php_source(release_root=release_root,entry=False)
    # Deliberately no main(), perform(), connection() or runtimeRun() invocation.
    return code+'\necho json_encode(["startup"=>"PASS","php"=>PHP_VERSION,"pdo_mysql"=>in_array("mysql",\\PDO::getAvailableDrivers(),true)]);'

def execute(env,paramiko):
    expected=env.get("MOSA_DIAG_EXPECTED_COMMIT","")
    if not re.fullmatch(r"[0-9a-f]{40}",expected) or env.get("GITHUB_SHA")!=expected or env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_RUN_ATTEMPT")!="1" or env.get("GITHUB_EVENT_NAME")!="workflow_dispatch" or env.get("GITHUB_REPOSITORY")!="masterxfix/MOSA-2":
        raise PermissionError("DIAGNOSTIC_BINDING")
    if live.release.git(live.ROOT,"rev-parse","HEAD").decode().strip()!=expected:raise PermissionError("CHECKOUT_BINDING")
    config=shared.configuration(env);manifest=live.package()
    logging.getLogger("paramiko").disabled=True
    r=dict(ok=False,diagnostic_commit=expected,collector_calls=0,provider_requests=0,business_writes=0,remote_files_written=0)
    with shared.ssh_client(config,r,paramiko) as transport:
        with paramiko.SFTPClient.from_transport(transport) as sftp:
            sftp.get_channel().settimeout(12)
            r["release_before"]=live.private.readback(sftp,live.RELEASE,manifest)
            r["run_before"]=fingerprint(sftp)
        command=shlex.join(["/opt/alt/python311/bin/python3.11","-I","-B","-c",PROBE])
        code,out,err,ms=remote.remote_call(transport,command,json.dumps(dict(source=startup_source(),release=live.RELEASE)).encode(),timeout=40)
        if code or err:raise RuntimeError("HARMLESS_PROBE_RECEIPT")
        r["startup_probe"]=json.loads(out)
        # Separate process/channel: DB secret never reaches the harmless startup test.
        code,out,err,ms=remote.remote_call(transport,remote.command("/opt/plesk/php/8.4/bin/php",DB.replace("@RELEASE@",live.RELEASE)),
            json.dumps(dict(password=env["MOSA_TEST_DB_PASSWORD"])).encode(),timeout=45)
        if code or err:raise RuntimeError("READ_ONLY_DB_RECEIPT")
        r["database"]=json.loads(out)
        with paramiko.SFTPClient.from_transport(transport) as sftp:
            sftp.get_channel().settimeout(12)
            r["run_after"]=fingerprint(sftp)
            r["run_unchanged"]="PASS" if r["run_before"]==r["run_after"] else "FAIL"
            r["release_after"]=live.private.readback(sftp,live.RELEASE,manifest)
        r["ok"]=r["run_unchanged"]=="PASS" and r["database"].get("ok") is True
    return r

def main():
    import paramiko
    try:r=execute(os.environ,paramiko)
    except Exception:r=dict(ok=False,failure_code="DIAGNOSTIC_STOPPED",collector_calls=0,provider_requests=0,business_writes=0)
    encoded=shared.public_text(r,os.environ);print(encoded,flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as f:f.write("Read-only PNE startup investigation\n\n~~~json\n"+encoded+"\n~~~\n")
    return 0 if r.get("ok") and json.loads(encoded).get("ok") else 1
if __name__=="__main__":raise SystemExit(main())
