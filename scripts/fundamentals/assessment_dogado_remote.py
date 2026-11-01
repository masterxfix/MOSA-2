"""Fileless Dogado process: never send private configuration/key across SSH."""
import subprocess
import types
CONFIG='/var/www/vhosts/web213.server10.configcenter.info/httpdocs/scharwerk.de/dashboard_neu/data/private/openai_config.php'
PHP='/opt/plesk/php/8.4/bin/php'

# Identical ordered policy in Python and PHP; parity covered by offline matrix tests.
def file_policy(m,uid,gid,path=None):
    if m['symlink']:return 'CONFIG_SYMLINK'
    if m['type']!=stat.S_IFREG:return 'CONFIG_NOT_REGULAR'
    if m['uid']!=uid:return 'CONFIG_OWNER'
    if m['nlink']!=1:return 'CONFIG_HARDLINK'
    # User-authorized legacy exception for this exact existing file only.
    legacy=(path==CONFIG and uid==10317 and gid==1003 and m['uid']==10317 and m['gid']==1003 and m['mode']==0o644)
    if m['mode'] not in (0o600,0o640) and not legacy:return 'CONFIG_MODE'
    if m['mode']==0o640 and m['gid']!=gid:return 'CONFIG_GROUP_READ_UNTRUSTED'
    return 'PASS'

def parent_policy(m,uid):
    if m['symlink']:return 'PARENT_SYMLINK'
    if m['type']!=stat.S_IFDIR:return 'PARENT_NOT_DIRECTORY'
    if m['uid'] not in (0,uid):return 'PARENT_OWNER'
    if m['mode'] & 0o7022:return 'PARENT_WRITABLE_OR_SPECIAL'
    return 'PASS'

def metadata(s):
    return dict(type=stat.S_IFMT(s.st_mode),uid=s.st_uid,gid=s.st_gid,mode=stat.S_IMODE(s.st_mode),mode_octal=format(stat.S_IMODE(s.st_mode),'04o'),symlink=stat.S_ISLNK(s.st_mode),nlink=s.st_nlink)

def identity(s):
    return tuple(getattr(s,'st_'+k) for k in ('dev','ino','mode','uid','gid','size','mtime_ns','ctime_ns','nlink'))

def protection_diagnosis(report):
    process=dict(uid=os.getuid(),euid=os.geteuid(),gid=os.getgid(),egid=os.getegid())
    diag=dict(process=process,parents=[],first_failure='PASS')
    report['config_metadata']=diag
    if process!={'uid':UID,'euid':UID,'gid':GID,'egid':GID}:raise RuntimeError('CONFIG_PROCESS_IDENTITY')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        root=metadata(os.fstat(fd));root['index']=0;root['status']=parent_policy(root,UID);diag['parents'].append(root)
        if root['status']!='PASS':diag['first_failure']=root['status'];raise RuntimeError(root['status'])
        parts=CONFIG.strip('/').split('/')
        for index,part in enumerate(parts[:-1],1):
            m=metadata(os.stat(part,dir_fd=fd,follow_symlinks=False));m['index']=index;m['status']=parent_policy(m,UID);diag['parents'].append(m)
            if m['status']!='PASS':diag['first_failure']=m['status'];raise RuntimeError(m['status'])
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=next_fd
        before=os.stat(parts[-1],dir_fd=fd,follow_symlinks=False);m=metadata(before);diag['file']=m
        diag['legacy_deviations']=[code for code,ok in [('FILE_TYPE',m['type']==stat.S_IFREG),('UID',m['uid']==UID),('GID',m['gid']==GID),('MODE',m['mode'] in (0o600,0o640))] if not ok]
        diag['readable']=os.access(CONFIG,os.R_OK,effective_ids=True)
        code=file_policy(m,UID,GID,CONFIG);diag['first_failure']=code
        if code!='PASS':raise RuntimeError(code)
        if m['mode']==0o644:
            report['security_risk']='LOCAL_READ_ISOLATION_UNPROVEN'
            # Exact-parent modes can prove world traversal, never full isolation.
            if all(p['mode'] & 0o001 for p in diag['parents']):
                diag['first_failure']='CONFIG_OTHER_READ_ACCESS';raise RuntimeError('CONFIG_OTHER_READ_ACCESS')
        # Metadata and access checks only; no file bytes are read here.
        if not diag['readable']:diag['first_failure']='CONFIG_NOT_READABLE';raise RuntimeError('CONFIG_NOT_READABLE')
        f=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            if identity(os.fstat(f))!=identity(before):raise RuntimeError('CONFIG_CHANGED')
        finally:os.close(f)
        report['protection_policy']='PASS'
        return diag
    finally:os.close(fd)

PHP_POLICY=r'''function filePolicy($m,$uid,$gid,$path=null){
if($m['symlink'])return 'CONFIG_SYMLINK';
if($m['type']!==0100000)return 'CONFIG_NOT_REGULAR';
if($m['uid']!==$uid)return 'CONFIG_OWNER';
if($m['nlink']!==1)return 'CONFIG_HARDLINK';
$legacy=$path==='/var/www/vhosts/web213.server10.configcenter.info/httpdocs/scharwerk.de/dashboard_neu/data/private/openai_config.php'&&$uid===10317&&$gid===1003&&$m['uid']===10317&&$m['gid']===1003&&$m['mode']===0644;
if(!in_array($m['mode'],[0600,0640],true)&&!$legacy)return 'CONFIG_MODE';
if($m['mode']===0640&&$m['gid']!==$gid)return 'CONFIG_GROUP_READ_UNTRUSTED';
return 'PASS';}
function parentPolicy($m,$uid){
if($m['symlink'])return 'PARENT_SYMLINK';
if($m['type']!==0040000)return 'PARENT_NOT_DIRECTORY';
if(!in_array($m['uid'],[0,$uid],true))return 'PARENT_OWNER';
if(($m['mode']&07022)!==0)return 'PARENT_WRITABLE_OR_SPECIAL';
return 'PASS';}
function meta($s){return ['type'=>$s['mode']&0170000,'uid'=>$s['uid'],'gid'=>$s['gid'],'mode'=>$s['mode']&07777,'symlink'=>($s['mode']&0170000)===0120000,'nlink'=>$s['nlink']];}
'''
PHP_KEY=PHP_POLICY+r'''$p="/var/www/vhosts/web213.server10.configcenter.info/httpdocs/scharwerk.de/dashboard_neu/data/private/openai_config.php";
try{
if(realpath($p)!==$p)exit(2);
$parents=[];$d=dirname($p);while(true){$parents[]=$d;if($d==='/')break;$d=dirname($d);}
foreach($parents as $d){$s=lstat($d);if(!$s||parentPolicy(meta($s),10317)!=='PASS')exit(2);}
$s=lstat($p);if(!$s||filePolicy(meta($s),10317,1003,$p)!=='PASS')exit(2);
$hash=hash_file('sha256',$p);ob_start();try{$v=(static function($path){return require $path;})($p);}finally{ob_end_clean();}
if(!is_array($v)||!isset($v['OPENAI_API_KEY'])||!is_string($v['OPENAI_API_KEY'])||trim($v['OPENAI_API_KEY'])==='')exit(3);
clearstatcache(true,$p);$after=lstat($p);foreach(['dev','ino','mode','uid','gid','size','mtime','ctime','nlink'] as $k)if($s[$k]!==$after[$k])exit(4);if(hash_file('sha256',$p)!==$hash)exit(4);
$identity=[];foreach(['dev','ino','mode','uid','gid','size','mtime','ctime','nlink'] as $k)$identity[$k]=$s[$k];
echo json_encode(['key'=>trim($v['OPENAI_API_KEY']),'hash'=>$hash,'identity'=>$identity],JSON_THROW_ON_ERROR);
}catch(Throwable){exit(5);}'''

def existing_key(report=None):
    report={} if report is None else report
    try:protection_diagnosis(report)
    except (FileNotFoundError,PermissionError):raise RuntimeError('CONFIG_NOT_VISIBLE_OR_READABLE') from None
    try:r=subprocess.run([PHP,'-n','-d','display_errors=0','-d','log_errors=0','-r',PHP_KEY],capture_output=True,timeout=15)
    except Exception:raise RuntimeError('CONFIG_PHP_UNAVAILABLE') from None
    if r.returncode:raise RuntimeError({2:'CONFIG_PATH_OR_PROTECTION',3:'CONFIG_KEY_MISSING',4:'CONFIG_CHANGED',5:'CONFIG_PHP_FAILED'}.get(r.returncode,'CONFIG_LOADER_FAILED'))
    if r.stderr or len(r.stdout)>8192:raise RuntimeError('CONFIG_LOADER_FAILED')
    try:return json.loads(r.stdout)
    except Exception:raise RuntimeError('CONFIG_LOADER_FAILED') from None

def load_modules(bundle):
    package=types.ModuleType('mosa_pilot');package.__path__=[];sys.modules['mosa_pilot']=package
    for name in ('assessment','responses_transport'):
        module=types.ModuleType('mosa_pilot.'+name);module.__package__='mosa_pilot';sys.modules[module.__name__]=module
        exec(compile(bundle[name],'<reviewed-mosa2-'+name+'>','exec'),module.__dict__)
    return sys.modules['mosa_pilot.assessment'],sys.modules['mosa_pilot.responses_transport']

def dogado_pilot(data):
    report=dict(ok=False,model_calls=0,key_transferred=False,db_writes=0,cost_status='NOT_CALLED');phase='BINDING';key=''
    try:
        if len(json.dumps(data).encode())>65536:raise RuntimeError('INPUT_BOUND')
        if data['marker']['execution']!='fundamentals-ai-droneshield-existing-mosa-20261101-01':raise RuntimeError('PILOT_BINDING')
        a,t=load_modules(data['modules']);snapshot=data['snapshot'];prepared,sha=a.prepare(snapshot)
        a.need(snapshot['identity']['isin']==['AU000000DRO2'] and len(prepared['facts'])==14 and len(snapshot['current_observation_ids'])==7,'PILOT_BINDING')
        a.need(sha==data['marker']['input_digest'],'INPUT_DIGEST')
        phase='CONFIG_METADATA';conf=existing_key(report);key=conf['key'];report['server_key_usable']=True
        phase='API_PREFLIGHT'
        class Observed:
            is_live=True
            def __init__(self):self.inner=t.OpenAIResponsesTransport(key,live_authorized=True)
            def __call__(self,request,**kwargs):
                report['model_calls']=1;report['cost_status']='UNKNOWN'
                r=self.inner(request,**kwargs)
                report.update(response_status=r.get('status') if r.get('status') in ('completed','incomplete','failed') else 'UNEXPECTED',actual_model=r.get('model') if r.get('model')=='gpt-6.1-sol' else 'UNEXPECTED')
                usage=r.get('usage')
                if type(usage) is dict:
                    report['usage']={k:usage[k] for k in ('input_tokens','output_tokens','total_tokens') if type(usage.get(k)) is int and usage[k]>=0}
                return r
        def preflight(request,budget,p,meta):
            nonlocal phase
            echo=dict(meta,factual_claims=[dict(observation_id=f['observation_id'],metric_key=f['metric'],value=f['value'],unit_key=f['unit'],source_id=f['source_id'],origin=f['origin'],rounded=f['rounded']) for f in p['facts']],calculation_claims=[dict(calculation_id=c['calculation_id'],value=c['value']) for c in p['calculations']])
            a.validate(echo,p,sha,meta['model_id'],meta['invocation_id'],meta['generated_at']);a.need(len(a.canonical(echo).encode())<=12000,'OUTPUT_PREFLIGHT_BOUND')
            report['cost_upper_bound']=budget
            phase='PRIVATE_RESERVATION'
            try:reserve_ai(data['marker'])
            except FileExistsError:raise RuntimeError('MARKER_ALREADY_CONSUMED') from None
            phase='MODEL_POST_AND_VALIDATION'
        from datetime import datetime,timezone
        result=a.ResponsesAdapter(Observed(),max_output_tokens=4000).assess(snapshot,price=data['price'],now=datetime.now(timezone.utc),invocation_id=data['invocation_id'],authorized_digest=sha,preflight=preflight)
        phase='OUTPUT_VALIDATED';assessment=result['assessment'];a.need(bool(assessment['interpretations']),'INTERPRETATIONS_MISSING')
        facts={f['observation_id']:f for f in prepared['facts']};calcs={c['calculation_id']:c for c in prepared['calculations']}
        details={}
        for item in assessment['interpretations']:
            refs=set(item['observation_ids'])
            for ref in item['calculation_ids']:refs.update(calcs[ref]['observation_ids'])
            entry=details.setdefault(item['code'],dict(metrics=set(),periods=set()))
            entry['metrics'].update(facts[r]['metric'] for r in refs);entry['periods'].update(facts[r]['end'] for r in refs)
        # Deterministic metadata from validated codes/references, never model prose.
        report.update(interpretation_details=[dict(code=c,metrics=sorted(v['metrics']),periods=sorted(v['periods'])) for c,v in sorted(details.items())],uncertainties=assessment['uncertainties'],missing_information=assessment['missing_information'],reasoning='medium',input_digest_verified='PASS')
        report.update(input_digest=sha,structured_output='PASS',fact_references='PASS',calculation_references='PASS',source_binding='PASS',interpretation_codes=sorted({i['code'] for i in assessment['interpretations']}),facts=len(assessment['factual_claims']),calculations=len(assessment['calculation_claims']),usage={k:result['usage'][k] for k in ('input_tokens','output_tokens','total_tokens') if k in result['usage']},actual_cost_upper_bound_usd=result['actual_cost_upper_bound_usd'],cost_status='CONSERVATIVE_ESTIMATE')
        phase='CONFIG_READBACK';after=existing_key();a.need(after['hash']==conf['hash'] and after['key']==key and after['identity']==conf['identity'],'CONFIG_CHANGED')
        report.update(ok=True,stage='SUCCESS',mosa_unchanged=True)
    except Exception as error:
        allowed={'CONFIG_OTHER_READ_ACCESS','CONFIG_PROCESS_IDENTITY','CONFIG_SYMLINK','CONFIG_NOT_REGULAR','CONFIG_OWNER','CONFIG_HARDLINK','CONFIG_MODE','CONFIG_GROUP_READ_UNTRUSTED','CONFIG_NOT_READABLE','PARENT_SYMLINK','PARENT_NOT_DIRECTORY','PARENT_OWNER','PARENT_WRITABLE_OR_SPECIAL','MARKER_ALREADY_CONSUMED','CONFIG_PATH_OR_PROTECTION','CONFIG_KEY_MISSING','CONFIG_PHP_FAILED','CONFIG_NOT_VISIBLE_OR_READABLE','CONFIG_PROTECTION','CONFIG_PHP_UNAVAILABLE','CONFIG_LOADER_FAILED','CONFIG_CHANGED','INPUT_BOUND','PILOT_BINDING','INPUT_DIGEST','INPUT_TOKEN_BOUND','COST_LIMIT','STALE_PRICE','OUTPUT_PREFLIGHT_BOUND','MODEL_TRANSPORT_FAILED','MODEL_INCOMPLETE','MODEL_REFUSAL_OR_TOOL','OUTPUT_SCHEMA','INVOCATION_BINDING','FACT_REFERENCE','FACT_BINDING','INCOMPLETE_FACTS','CALCULATION_REFERENCE','CALCULATION_BINDING','INCOMPLETE_CALCULATIONS','INTERPRETATION_REFERENCE','INTERPRETATION_BINDING','MISSING_BINDING','USAGE_MISSING','USAGE_INVALID','USAGE_OVER_BUDGET','INTERPRETATIONS_MISSING'}
        report.update(stage=phase,error_code=str(error) if str(error) in allowed else 'DOGADO_PILOT_STOP_NO_RETRY')
    # No remote stdout/stderr, key or config text is forwarded; only this allowlisted report.
    raw=json.dumps(report,ensure_ascii=True)
    if key and key in raw:return dict(ok=False,error_code='SECRET_OUTPUT_BLOCKED',model_calls=report['model_calls'])
    return report
if __name__=='__main__':
    try:
        data=json.loads(sys.stdin.read(65537));print(json.dumps(dogado_pilot(data)))
    except Exception:print(json.dumps(dict(ok=False,error_code='REMOTE_INPUT_FAILED',model_calls=0)))
