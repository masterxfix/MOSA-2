<?php
declare(strict_types=1);
/** Fileless PHP -> Python -> PHP capability check; no DB or provider code. */
function readinessChild(array $command,string $input): array {
    $env=['PATH'=>(string)getenv('PATH'),'PYTHONDONTWRITEBYTECODE'=>'1'];
    $pipes=[];$p=@proc_open($command,[0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes,null,$env,['bypass_shell'=>true]);
    if(!is_resource($p))return ['started'=>false,'failure'=>'PROC_OPEN_FAILED'];
    $out='';$errBytes=0;$timeout=false;$overflow=false;$exit=-1;$start=hrtime(true);
    try{
        if(fwrite($pipes[0],$input)!==strlen($input))throw new RuntimeException('child_stdin');
        fclose($pipes[0]);unset($pipes[0]);
        stream_set_blocking($pipes[1],false);stream_set_blocking($pipes[2],false);
        while(true){
            $out.=stream_get_contents($pipes[1],4096);$errBytes+=strlen(stream_get_contents($pipes[2],4096));
            $status=proc_get_status($p);
            if(strlen($out)>32768||$errBytes>32768){$overflow=true;break;}
            if(!$status['running']){
                if($status['exitcode']>=0)$exit=$status['exitcode'];
                if(feof($pipes[1])&&feof($pipes[2]))break;
            }
            if((hrtime(true)-$start)/1e9>15){$timeout=true;break;}
            usleep(10000);
        }
    }finally{
        $status=proc_get_status($p);
        if($status['running']){
            proc_terminate($p,15);
            for($i=0;$i<20&&proc_get_status($p)['running'];$i++)usleep(10000);
            if(proc_get_status($p)['running'])proc_terminate($p,9);
        }
        foreach($pipes as $pipe)fclose($pipe);
        $closed=proc_close($p);if($exit<0)$exit=$closed;
    }
    if($timeout||$overflow||$errBytes>0||$exit!==0)return ['started'=>true,'exit_code'=>$exit,'timeout'=>$timeout,
        'output_limit'=>$overflow,'stderr_suppressed'=>$errBytes>0];
    try{$result=json_decode($out,true,32,JSON_THROW_ON_ERROR);}
    catch(Throwable){return ['started'=>true,'failure'=>'CHILD_OUTPUT_INVALID','exit_code'=>$exit];}
    return ['started'=>true,'exit_code'=>$exit,'result'=>$result,'elapsed_ms'=>(hrtime(true)-$start)/1e6];
}
function readinessProbe(array $input,?callable $child=null): array {
    $r=['ok'=>false,'assessment_complete'=>false,'php_version'=>PHP_VERSION,'php_sapi'=>PHP_SAPI,
        'pdo_mysql'=>class_exists('PDO')&&in_array('mysql',PDO::getAvailableDrivers(),true),
        'provider_requests'=>0,'database_connections'=>0,'business_writes'=>0,'remote_file_operations'=>0];
    $r['php_functions']=[];
    foreach(['proc_open','proc_close','proc_get_status','proc_terminate','stream_set_blocking','stream_get_contents','json_decode','md5'] as $fn)
        $r['php_functions'][$fn]=function_exists($fn);
    $r['php_limits']=['memory_limit'=>ini_get('memory_limit'),'max_execution_time'=>ini_get('max_execution_time'),
        'hard_timeout'=>ini_get('hard_timeout'),'default_socket_timeout'=>ini_get('default_socket_timeout'),
        'open_basedir_restricted'=>ini_get('open_basedir')!==''];
    $r['posix_limits']=function_exists('posix_getrlimit')?posix_getrlimit():'UNAVAILABLE';
    $r['provider_primitives']=['md5'=>function_exists('md5'),'json'=>function_exists('json_encode')];
    try{$zone=new DateTimeZone('Europe/Berlin');$r['provider_primitives']['berlin_timezone']=$zone->getName()==='Europe/Berlin';}
    catch(Throwable){$r['provider_primitives']['berlin_timezone']=false;}
    if(PHP_VERSION_ID<80400||PHP_VERSION_ID>=80500||PHP_SAPI!=='cli'||!$r['pdo_mysql']){
        $r['blocker']='PHP84_CLI_PDO_REQUIRED';$r['assessment_complete']=true;return $r;
    }
    foreach(['proc_open','proc_close','proc_get_status','proc_terminate','stream_set_blocking','stream_get_contents'] as $fn)
        if(!$r['php_functions'][$fn]){$r['blocker']='REQUIRED_PROCESS_FUNCTION_DISABLED';$r['assessment_complete']=true;return $r;}
    if(!is_string($input['python_source']??null)||strlen($input['python_source'])>16384)throw new RuntimeException('probe_source_invalid');
    $child??=__NAMESPACE__.'readinessChild';
    $flags=['-d','display_errors=0','-d','log_errors=0','-d','auto_prepend_file=','-d','auto_append_file=','-d','opcache.enable_cli=0','-d','opcache.file_cache='];
    $stdin=json_encode(['php_binary'=>PHP_BINARY,'php_flags'=>$flags],JSON_THROW_ON_ERROR);
    $r['python_attempts']=[];
    foreach(['/usr/bin/python3','python3','/usr/local/bin/python3'] as $binary){
        $attempt=$child([$binary,'-I','-B','-c',$input['python_source']],$stdin);
        $r['python_attempts'][]=['command'=>$binary]+$attempt;
        if(($attempt['result']['ok']??false)===true&&$r['provider_primitives']['md5']&&$r['provider_primitives']['json']&&$r['provider_primitives']['berlin_timezone']){$r['ok']=true;$r['selected_python']=$attempt['result']['executable'];break;}
    }
    $r['assessment_complete']=true;
    if(!$r['ok'])$r['blocker']='NO_COMPATIBLE_PYTHON_STACK_IN_APPROVED_COMMANDS';
    return $r;
}
if(!defined('MOSA_READINESS_LIBRARY_ONLY')){
    ini_set('display_errors','0');ini_set('log_errors','0');
    try{echo json_encode(readinessProbe($mosa_input),JSON_THROW_ON_ERROR);}
    catch(Throwable){echo '{"ok":false,"assessment_complete":false,"failure":"READINESS_PROBE_FAILED"}';}
}
