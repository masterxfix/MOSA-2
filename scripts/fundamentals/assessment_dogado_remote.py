"""Fileless Dogado process: never send private configuration/key across SSH."""
import subprocess
import types
CONFIG='/var/www/vhosts/web213.server10.configcenter.info/httpdocs/scharwerk.de/dashboard_neu/data/private/openai_config.php'
PHP='/opt/plesk/php/8.4/bin/php'

# The documented old loader consumes an array with OPENAI_API_KEY. No old code is modified.
PHP_KEY=r'''$p="/var/www/vhosts/web213.server10.configcenter.info/httpdocs/scharwerk.de/dashboard_neu/data/private/openai_config.php";
try{
$s=lstat($p);if(!$s||realpath($p)!==$p||($s['mode']&0170000)!==0100000||$s['uid']!==10317||$s['gid']!==1003||!in_array($s['mode']&0777,[0600,0640],true))exit(2);
$hash=hash_file('sha256',$p);ob_start();try{$v=(static function($path){return require $path;})($p);}finally{ob_end_clean();}
if(!is_array($v)||!isset($v['OPENAI_API_KEY'])||!is_string($v['OPENAI_API_KEY'])||trim($v['OPENAI_API_KEY'])==='')exit(3);
clearstatcache(true,$p);$after=lstat($p);foreach(['dev','ino','mode','uid','gid','size','mtime','ctime'] as $k)if($s[$k]!==$after[$k])exit(4);if(hash_file('sha256',$p)!==$hash)exit(4);
echo json_encode(['key'=>trim($v['OPENAI_API_KEY']),'hash'=>$hash],JSON_THROW_ON_ERROR);
}catch(Throwable){exit(5);}'''

def existing_key():
    # Only the exact authorized configuration is inspected, no parent scans or alternative secrets.
    try:
        fd=os.open(CONFIG,os.O_RDONLY|os.O_NOFOLLOW)
    except (FileNotFoundError,PermissionError):raise RuntimeError('CONFIG_NOT_VISIBLE_OR_READABLE') from None
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or (s.st_uid,s.st_gid)!=(UID,GID) or stat.S_IMODE(s.st_mode) not in (0o600,0o640):raise RuntimeError('CONFIG_PROTECTION')
    finally:os.close(fd)
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
        if data['marker']['execution']!='fundamentals-ai-droneshield-dogado-20261101-01':raise RuntimeError('PILOT_BINDING')
        a,t=load_modules(data['modules']);snapshot=data['snapshot'];prepared,sha=a.prepare(snapshot)
        a.need(snapshot['identity']['isin']==['AU000000DRO2'] and len(prepared['facts'])==14 and len(snapshot['current_observation_ids'])==7,'PILOT_BINDING')
        a.need(sha==data['marker']['input_digest'],'INPUT_DIGEST')
        phase='CONFIG_READ';conf=existing_key();key=conf['key'];report['server_key_usable']=True
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
        report.update(input_digest=sha,structured_output='PASS',fact_references='PASS',calculation_references='PASS',source_binding='PASS',interpretation_codes=sorted({i['code'] for i in assessment['interpretations']}),facts=len(assessment['factual_claims']),calculations=len(assessment['calculation_claims']),usage={k:result['usage'][k] for k in ('input_tokens','output_tokens','total_tokens') if k in result['usage']},actual_cost_upper_bound_usd=result['actual_cost_upper_bound_usd'],cost_status='CONSERVATIVE_ESTIMATE')
        phase='CONFIG_READBACK';after=existing_key();a.need(after['hash']==conf['hash'] and after['key']==key,'CONFIG_CHANGED')
        report.update(ok=True,stage='SUCCESS',mosa_unchanged=True)
    except Exception as error:
        allowed={'MARKER_ALREADY_CONSUMED','CONFIG_PATH_OR_PROTECTION','CONFIG_KEY_MISSING','CONFIG_PHP_FAILED','CONFIG_NOT_VISIBLE_OR_READABLE','CONFIG_PROTECTION','CONFIG_PHP_UNAVAILABLE','CONFIG_LOADER_FAILED','CONFIG_CHANGED','INPUT_BOUND','PILOT_BINDING','INPUT_DIGEST','INPUT_TOKEN_BOUND','COST_LIMIT','STALE_PRICE','OUTPUT_PREFLIGHT_BOUND','MODEL_TRANSPORT_FAILED','MODEL_INCOMPLETE','MODEL_REFUSAL_OR_TOOL','OUTPUT_SCHEMA','INVOCATION_BINDING','FACT_REFERENCE','FACT_BINDING','INCOMPLETE_FACTS','CALCULATION_REFERENCE','CALCULATION_BINDING','INCOMPLETE_CALCULATIONS','INTERPRETATION_REFERENCE','INTERPRETATION_BINDING','MISSING_BINDING','USAGE_MISSING','USAGE_INVALID','USAGE_OVER_BUDGET','INTERPRETATIONS_MISSING'}
        report.update(stage=phase,error_code=str(error) if str(error) in allowed else 'DOGADO_PILOT_STOP_NO_RETRY')
    # No remote stdout/stderr, key or config text is forwarded; only this allowlisted report.
    raw=json.dumps(report,ensure_ascii=True)
    if key and key in raw:return dict(ok=False,error_code='SECRET_OUTPUT_BLOCKED',model_calls=report['model_calls'])
    return report
if __name__=='__main__':
    try:
        data=json.loads(sys.stdin.read(65537));print(json.dumps(dogado_pilot(data)))
    except Exception:print(json.dumps(dict(ok=False,error_code='REMOTE_INPUT_FAILED',model_calls=0)))
