"""Fileless synthetic module probe. Never an acquisition or persistence launcher."""
import base64
import hashlib
import importlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

RELEASE_COMMIT="92274a79550b8acd719434459022da6de5261d2e"
RELEASE="/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector/releases/"+RELEASE_COMMIT
PYTHON="/opt/alt/python311/bin/python3.11"
PHP="/opt/plesk/php/8.4/bin/php"
DENY="exec,system,shell_exec,passthru,popen,curl_exec,curl_multi_exec,fsockopen,pfsockopen,stream_socket_client,stream_socket_server,mail,error_log,syslog,tmpfile,tempnam,fwrite,fputs,fflush,truncate,ftruncate,file_put_contents,fopen,unlink,rename,mkdir,rmdir,chmod,chown,touch,copy,symlink,link"
PHP_OPTIONS=("-n","-d","log_errors=0","-d","display_errors=stderr","-d","opcache.enable_cli=0",
    "-d","opcache.file_cache=","-d","allow_url_fopen=0","-d","allow_url_include=0",
    "-d","memory_limit=64M","-d","max_execution_time=10","-d","disable_classes=PDO,mysqli",
    "-d","disable_functions="+DENY)
ORIGINAL_RUN=subprocess.run
ALLOWED_COMMANDS=set()
COUNTERS=dict(php_processes=0,blocked_network=0,blocked_writes=0)

def need(ok,code):
    if not ok:raise ValueError(code)

def php_run(php,tail,**kwargs):
    command=[php,*PHP_OPTIONS,*tail]
    ALLOWED_COMMANDS.add(tuple(command))
    result=ORIGINAL_RUN(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        timeout=10,env=dict(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin",
                           PYTHONDONTWRITEBYTECODE="1",PHP_INI_SCAN_DIR=""),**kwargs)
    need(result.returncode==0 and not result.stderr,"PHP_PROCESS_FAILED")
    need(len(result.stdout)<=32768,"PHP_OUTPUT_LIMIT")
    return result.stdout

def pinned_run(args,**kwargs):
    need(type(args) is list and len(args)==2 and args[0]=="php"
         and args[1]==VALUE_ADAPTER,"UNAPPROVED_CHILD")
    COUNTERS["php_processes"]+=1
    need(COUNTERS["php_processes"]<=256,"PROCESS_BUDGET")
    data=json.loads(kwargs["input"])
    need(data["operation"] in ("identity","timestamp","values","legacy"),"VALUE_OPERATION")
    output=php_run(PHP_BINARY,["-d","disable_functions="+DENY+",proc_open",args[1]],
                   input=kwargs["input"])
    return subprocess.CompletedProcess(args,0,output,b"")

def audit(event,args):
    if event.startswith("socket.") or event in ("sqlite3.connect","os.system","os.exec","os.posix_spawn"):
        COUNTERS["blocked_network"]+=1
        raise PermissionError("NETWORK_OR_UNAPPROVED_PROCESS_FORBIDDEN")
    if event=="subprocess.Popen":
        need(tuple(args[1]) in ALLOWED_COMMANDS,"UNAPPROVED_PROCESS")
    # subprocess stdio opens existing anonymous pipe descriptors, not files.
    if event=="open" and type(args[0]) is int and stat.S_ISFIFO(os.fstat(args[0]).st_mode):
        return
    if (event=="open" and (any(c in (args[1] or "") for c in "wax+")
        or (args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))) or event in (
            "os.mkdir","os.rename","os.remove","os.rmdir","os.chmod","os.chown",
            "os.symlink","os.link","os.utime","os.truncate"):
        COUNTERS["blocked_writes"]+=1
        raise PermissionError("FILESYSTEM_WRITE_FORBIDDEN")

def integrity(root,manifest,remote=True):
    need(manifest["commit"]==RELEASE_COMMIT and len(manifest["files"])==33
         and manifest["payload_bytes"]==248105,"MANIFEST_BINDING")
    root=Path(root)
    need(not root.is_symlink() and root.resolve()==root and stat.S_IMODE(root.stat().st_mode)==0o700,"RELEASE_PATH")
    if remote:need((root.stat().st_uid,root.stat().st_gid)==(10317,1003),"RELEASE_ROOT_OWNER")
    expected={row["path"]:row for row in manifest["files"]}
    dirs={str(p) for name in expected for p in Path(name).parents if str(p)!="."}
    seen=set()
    for current,children,files in os.walk(root,followlinks=False):
        for name in children+files:
            p=Path(current)/name;s=p.lstat();rel=p.relative_to(root).as_posix()
            need(not stat.S_ISLNK(s.st_mode),"RELEASE_SYMLINK")
            if remote:need((s.st_uid,s.st_gid)==(10317,1003),"RELEASE_OWNER")
            if stat.S_ISDIR(s.st_mode):
                need(rel in dirs and stat.S_IMODE(s.st_mode)==0o700,"RELEASE_DIRECTORY")
            else:
                need(rel in expected and stat.S_ISREG(s.st_mode)
                     and stat.S_IMODE(s.st_mode)==0o600,"RELEASE_FILE")
                row=expected[rel]
                need(s.st_size==row["size"] and hashlib.sha256(p.read_bytes()).hexdigest()==row["sha256"],"RELEASE_HASH")
                seen.add(rel)
    need(seen==set(expected),"RELEASE_SET")
    return "PASS"

def evaluate(root,cases):
    global VALUE_ADAPTER
    VALUE_ADAPTER=str(Path(root)/"scripts/phase3n/value_adapter.php")
    sys.path.insert(0,str(root))
    from scripts.market_collector.contracts import Request,RouteContract,TransportResponse
    from scripts.market_collector.collector import FixtureTransport
    from scripts.market_collector.normalizer import pipeline,writer
    catalog=writer.observation.catalog_module.normative_catalog()
    results=[]
    for case in cases:
        adapter=getattr(importlib.import_module(case["module"]),case["adapter"])()
        request=Request(**case["request"])
        route=RouteContract(request.provider_key,request.instrument,2,case["route"])
        response=TransportResponse(base64.b64decode(case["payload"],validate=True),
                                   case["collected_at"],200,"application/json")
        result=pipeline(request,route,FixtureTransport({request:response}),[adapter],
                        catalog=catalog,created_at=case["created_at"])
        need(result["decision"]=="INSERT" and result["normalizer_status"]=="NORMALIZED","INSERT_PLAN")
        plan=result["writer_plan"]
        replay=writer.WriterPlanner(catalog,[route.envelope()],[dict(format_version=2,
            payload=plan["normalized"],dedupe_key=plan["dedupe_key"])]).plan(
                plan["normalized"],format_version=2,intent="NEW_NATIVE_V2",created_at=case["created_at"])
        need(replay["decision"]=="DUPLICATE_UNCHANGED"
             and replay["canonical_bytes"]==plan["canonical_bytes"]
             and replay["dedupe_key"]==plan["dedupe_key"],"REPLAY")
        results.append(dict(normalized=plan["normalized"],canonical_hex=plan["canonical_bytes"].hex(),
            dedupe_hex=plan["dedupe_key"].hex(),insert=plan["decision"],replay=replay["decision"],
            catalog_fingerprint=catalog.fingerprint))
    return results

def php_modules(root,manifest):
    paths=[r["path"] for r in manifest["files"] if r["path"].endswith(".php")]
    # This request-descriptor file has an unconditional stdio main: syntax only.
    for path in paths:php_run(PHP,["-l",str(root/path)])
    libraries=[p for p in paths if p!="scripts/market_collector/frankfurt_request.php"]
    code=("foreach(json_decode("+json.dumps(json.dumps(libraries))+ ",true) as $p)require_once "+
          json.dumps(str(root)+"/") +".$p;")
    code+=" $c=\\Mosa2\\CollectorRelease\\configuration("+json.dumps(str(root))+");"
    code+="echo json_encode(['php'=>PHP_VERSION,'binary'=>PHP_BINARY,'python'=>$c['python'],'included'=>get_included_files()]);"
    result=json.loads(php_run(PHP,["-r",code]))
    need(result["php"]=="8.4.12" and os.path.realpath(result["binary"])==os.path.realpath(PHP)
         and result["python"]==PYTHON,"PHP_PYTHON_PIN")
    need({str(Path(p).relative_to(root)) for p in result["included"]}==set(libraries),"PHP_INCLUDE_SET")
    return dict(status="PASS",libraries=len(libraries),syntax_files=len(paths),
                php_to_python="PASS",php=result["php"],python="3.11.17")

def run(request):
    global PHP_BINARY
    need(request["root"]==RELEASE,"FIXED_RELEASE_ONLY")
    need(sys.version_info[:3]==(3,11,17) and os.path.realpath(sys.executable)==os.path.realpath(PYTHON),"PYTHON_PIN")
    import resource
    resource.setrlimit(resource.RLIMIT_CPU,(25,25))
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    def deadline(signum,frame):raise TimeoutError("OFFLINE_WALL_LIMIT")
    signal.signal(signal.SIGALRM,deadline)
    signal.alarm(55)
    os.environ.clear()
    os.environ.update(PATH="/opt/plesk/php/8.4/bin:/usr/bin:/bin",PYTHONDONTWRITEBYTECODE="1",PHP_INI_SCAN_DIR="")
    sys.dont_write_bytecode=True
    PHP_BINARY=PHP
    root=Path(RELEASE)
    before=integrity(root,request["manifest"])
    sys.addaudithook(audit)
    subprocess.run=pinned_run
    sys.path.insert(0,str(root))
    imported=[]
    for row in request["manifest"]["files"]:
        if row["path"].endswith(".py"):
            module=importlib.import_module(row["path"][:-3].replace("/","."))
            need(Path(module.__file__).resolve()==root/row["path"],"IMPORT_ORIGIN")
            imported.append(row["path"])
    php=php_modules(root,request["manifest"])
    results=evaluate(root,request["cases"])
    need(results==request["expected"],"REFERENCE_COMPARISON")
    after=integrity(root,request["manifest"])
    need(COUNTERS["blocked_network"]==COUNTERS["blocked_writes"]==0,"UNEXPECTED_IO_ATTEMPT")
    signal.alarm(0)
    return dict(ok=True,release=RELEASE,commit=RELEASE_COMMIT,integrity_before=before,integrity_after=after,
        python_modules=dict(status="PASS",count=len(imported)),php_modules=php,
        python_to_php="PASS",normalizer="PASS",insert="PASS",replay="DUPLICATE_UNCHANGED",
        comparison="PASS",cases=results,counters=COUNTERS,
        database_connections=0,provider_requests=0,remote_files_written=0,
        scope="SYNTHETIC_IN_MEMORY_ONLY")

if __name__=="__main__":
    try:
        request=json.loads(sys.stdin.read(65537))
        need(len(request["cases"])==2,"BOUNDED_SYNTHETIC_CASES")
        result=run(request)
    except Exception as error:
        result=dict(ok=False,failure_type=type(error).__name__,failure=str(error)[:160])
    print(json.dumps(result,sort_keys=True))
