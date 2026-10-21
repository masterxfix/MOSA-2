"""Bounded interpreter/ABI assessment. No installation, upload, DB or provider."""
import json
import logging
import os
from pathlib import Path
import sys

import collector_actions as shared
import collector_db_locality as remote
import collector_runtime_readiness as readiness

ROOT=Path(__file__).resolve().parents[1]
VERSIONS=('3.12','3.13','3.14','3.15','3.11','3.10')
CANDIDATES=tuple(path for v in VERSIONS for path in
    ('/usr/bin/python'+v,'/usr/local/bin/python'+v,'/opt/alt/python'+v.replace('.','')+'/bin/python'+v))
PLATFORM_PROBE = '''import ctypes
import json
import os
import struct
import sys
r={'version':sys.version.split()[0],'version_info':list(sys.version_info[:3]),'executable':sys.executable,
   'machine':os.uname().machine,'pointer_bits':struct.calcsize('P')*8,'byteorder':sys.byteorder,
   'provider_requests':0,'database_connections':0}
try:
    r['libc']=os.confstr('CS_GNU_LIBC_VERSION')
except Exception:
    r['libc']='UNKNOWN'
r['libraries']={}
for name in ('libc.so.6','libpthread.so.0','libdl.so.2','libutil.so.1','librt.so.1','libm.so.6','libcrypt.so.1'):
    try:
        ctypes.CDLL(name)
        r['libraries'][name]='LOADABLE'
    except Exception:
        r['libraries'][name]='UNAVAILABLE'
r['loader_accessible']=os.access('/lib64/ld-linux-x86-64.so.2',os.R_OK)
print(json.dumps(r,sort_keys=True))
'''
VERSION_PROBE='import json,sys;print(json.dumps(dict(version=sys.version.split()[0],version_info=list(sys.version_info[:3]),executable=sys.executable)))'
PHP_LOGIC = r'''
function provisionProbe(array $input,?callable $exists=null,?callable $child=null): array {
    $exists??='is_executable';$child??='readinessChild';
    foreach(['platform_source','module_source','version_source'] as $key)
        if(!is_string($input[$key]??null)||strlen($input[$key])>16384)throw new RuntimeException('invalid_source');
    $started=hrtime(true);
    $r=['assessment_complete'=>false,'compatible_python_found'=>false,'provider_requests'=>0,
        'database_connections'=>0,'business_writes'=>0,'remote_file_operations'=>0,'candidates'=>[]];
    $r['php_version']=PHP_VERSION;
    if(!function_exists('proc_open')||!function_exists('proc_terminate')||!function_exists('proc_get_status')){
        $r['blocker']='PROCESS_FUNCTION_UNAVAILABLE';$r['assessment_complete']=true;return $r;
    }
    $r['selector_commands']=[];
    foreach(['/usr/bin/cloudlinux-selector','/usr/bin/selectorctl'] as $path)$r['selector_commands'][$path]=$exists($path);
    if($exists('/usr/bin/python3')){
        $r['platform']=$child(['/usr/bin/python3','-I','-B','-c',$input['platform_source']],'');
    }else $r['platform']=['failure'=>'BASELINE_INTERPRETER_UNAVAILABLE'];
    $versions=['3.12','3.13','3.14','3.15','3.11','3.10'];$paths=[];
    foreach($versions as $v)foreach(['/usr/bin/python'.$v,'/usr/local/bin/python'.$v,'/opt/alt/python'.str_replace('.','',$v).'/bin/python'.$v] as $path)$paths[]=$path;
    $flags=['-d','display_errors=0','-d','log_errors=0','-d','auto_prepend_file=','-d','auto_append_file=','-d','opcache.enable_cli=0','-d','opcache.file_cache='];
    $stdin=json_encode(['php_binary'=>PHP_BINARY,'php_flags'=>$flags],JSON_THROW_ON_ERROR);
    foreach($paths as $path){
        if((hrtime(true)-$started)/1e9>45){$r['blocker']='PROBE_BUDGET_EXHAUSTED';return $r;}
        $entry=['path'=>$path,'executable'=>$exists($path)];
        if($entry['executable']){
            $entry['version_probe']=$child([$path,'-I','-B','-c',$input['version_source']],'');
            $v=$entry['version_probe']['result']['version_info']??[];
            if(count($v)>=2&&($v[0]>3||($v[0]===3&&$v[1]>=10))){
                $entry['module_probe']=$child([$path,'-I','-B','-c',$input['module_source']],$stdin);
                if(($entry['module_probe']['result']['ok']??false)===true){
                    $r['compatible_python_found']=true;$r['selected_python']=$path;
                }
            }
        }
        $r['candidates'][]=$entry;
        if($r['compatible_python_found'])break;
    }
    $r['assessment_complete']=true;return $r;
}
if(!defined('MOSA_PROVISION_LIBRARY_ONLY')){
    try{echo json_encode(provisionProbe($mosa_input),JSON_THROW_ON_ERROR);}
    catch(Throwable){echo '{"assessment_complete":false,"failure":"PYTHON_OPTIONS_PROBE_FAILED"}';}
}
'''


def php_source():
    library,unused=readiness.sources()
    prefix='declare(strict_types=1);\n'
    if not library.startswith(prefix):
        raise remote.ProbeError('READINESS_LIBRARY_HEADER_INVALID')
    return prefix+"define('MOSA_READINESS_LIBRARY_ONLY',true);\n"+library[len(prefix):]+'\n'+PHP_LOGIC


def payload():
    unused,module_source=readiness.sources()
    return json.dumps(dict(source=php_source(),platform_source=PLATFORM_PROBE,module_source=module_source,
                           version_source=VERSION_PROBE)).encode('utf-8')


def execute(env,paramiko=None):
    report=dict(ok=False,stage='configuration',ssh='NOT_CHECKED',host_key='NOT_CHECKED',
                compatible_python_found=False,provider_requests=0,database_connections=0,
                business_writes=0,remote_file_operations=0)
    try:
        config=shared.configuration(env)
        if paramiko is None:
            import paramiko
        logging.getLogger('paramiko').disabled=True
        with shared.ssh_client(config,report,paramiko) as transport:
            report['stage']='php_capability';report['php_capability_attempts']=[]
            binary,attempts=remote.capability(transport,report['php_capability_attempts'])
            report['stage']='bounded_interpreter_abi_probe'
            code,output,errors,elapsed=remote.remote_call(transport,remote.command(binary,remote.BOOTSTRAP),payload(),timeout=90)
            if code or errors:
                raise remote.ProbeError('PYTHON_OPTIONS_PROCESS_FAILED')
            result=json.loads(output)
            report['probe']=result;report['command_elapsed_ms']=elapsed
            report['ok']=result.get('assessment_complete') is True
            report['compatible_python_found']=result.get('compatible_python_found') is True
        report['stage']='finished'
    except shared.ConfigurationError as error:
        report['failure']=str(error)
    except remote.ProbeError as error:
        report['failure']=str(error)
    except Exception as error:
        report['failure_type']=type(error).__name__
    report['secrets_in_log']='NEIN/PASS'
    return report


def main():
    result=execute(os.environ);text=shared.public_text(result,os.environ);print(text,flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as out:
            fence=chr(96)*3
            out.write('MOSA-2 bounded Python provisioning assessment\n\n'+fence+'json\n'+text+'\n'+fence+'\n')
    return 0 if result['ok'] and json.loads(text).get('ok') else 1


if __name__=='__main__':
    sys.exit(main())
