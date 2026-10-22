<?php
declare(strict_types=1);
namespace Mosa2\MarketCurrent;

/** Private anonymous files avoid blocking process pipes on Windows and Linux. */
function boundedPlanner(array $command,string $wire,array $config,float $seconds): string {
    $previous=umask(0077);$files=[];$proc=null;
    try{
        for($i=0;$i<3;$i++){
            $file=tmpfile();if($file===false)throw new \RuntimeException('current_planner_resource');
            $files[]=$file;
        }
        if(fwrite($files[0],$wire)!==strlen($wire))throw new \RuntimeException('current_planner_input');
        rewind($files[0]);
        $proc=proc_open($command,$files,$pipes,$config['project'],
            ['PATH'=>$config['runtime_path'],'PYTHONDONTWRITEBYTECODE'=>'1']);
        if(!is_resource($proc))throw new \RuntimeException('current_planner_process');
        $start=hrtime(true)/1e9;
        while(true){
            if(hrtime(true)/1e9-$start>$seconds)throw new \RuntimeException('current_planner_timeout');
            if(fstat($files[1])['size']+fstat($files[2])['size']>1048576)throw new \RuntimeException('current_planner_output_limit');
            $state=proc_get_status($proc);
            if(!$state['running'])break;
            usleep(10000);
        }
        rewind($files[1]);rewind($files[2]);$out=stream_get_contents($files[1]);$err=stream_get_contents($files[2]);
        if($state['exitcode']!==0||$err!==''||strlen($out)>1048576)throw new \RuntimeException('current_planner_failed');
        return $out;
    }finally{
        // Planner has no DB connection; nested PHP calls expire after 10/15s.
        // The outer hard timeout also kills the complete POSIX process group.
        if(is_resource($proc)){
            if(proc_get_status($proc)['running'])proc_terminate($proc,9);
            proc_close($proc);
        }
        foreach($files as $file)fclose($file);
        umask($previous);
    }
}
