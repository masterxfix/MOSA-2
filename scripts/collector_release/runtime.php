<?php
declare(strict_types=1);
namespace Mosa2\CollectorRelease;
require_once __DIR__.'/../market_collector/schema_contract.php';

/** Library-only binding for a future reviewed launcher; no batch is started. */
function configuration(string $project,int $schemaVersion=4): array {
    $state=\Mosa2\CollectorSchema5\selected(['state_contract'=>['schema_version'=>$schemaVersion]]);
    if(PHP_SAPI!=='cli'||PHP_VERSION!=='8.4.12'
        ||realpath(PHP_BINARY)!==realpath('/opt/plesk/php/8.4/bin/php'))
        throw new \RuntimeException('pinned_php_required');
    $python='/opt/alt/python311/bin/python3.11';
    $process=proc_open([$python,'-I','-B','-c',
        'import sys; print(".".join(map(str,sys.version_info[:3])))'],
        [0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes,null,
        ['PATH'=>'/opt/plesk/php/8.4/bin:/usr/bin:/bin','PYTHONDONTWRITEBYTECODE'=>'1']);
    if(!is_resource($process))throw new \RuntimeException('pinned_python_required');
    fclose($pipes[0]);stream_set_blocking($pipes[1],false);stream_set_blocking($pipes[2],false);
    $out='';$err='';$deadline=microtime(true)+5;$exit=-1;
    try {
        do {
            $out.=stream_get_contents($pipes[1]);$err.=stream_get_contents($pipes[2]);
            if(strlen($out)+strlen($err)>4096)throw new \RuntimeException('runtime_probe_output_limit');
            $status=proc_get_status($process);
            if(!$status['running']){$exit=$status['exitcode'];break;}
            if(microtime(true)>$deadline)throw new \RuntimeException('runtime_probe_timeout');
            usleep(10000);
        }while(true);
        $out.=stream_get_contents($pipes[1]);$err.=stream_get_contents($pipes[2]);
    }finally {
        if(proc_get_status($process)['running'])proc_terminate($process,9);
        fclose($pipes[1]);fclose($pipes[2]);proc_close($process);
    }
    if($exit!==0||trim($out)!=='3.11.17'||$err!=='')
        throw new \RuntimeException('pinned_python_required');
    return ['python'=>$python,'php'=>'/opt/plesk/php/8.4/bin/php','project'=>$project,'state_contract'=>$state,
        'runtime_path'=>'/opt/plesk/php/8.4/bin:/usr/bin:/bin',
        'request_script'=>$project.'/scripts/market_collector/frankfurt_request.php'];
}
