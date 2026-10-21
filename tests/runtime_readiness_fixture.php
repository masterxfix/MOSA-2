<?php
declare(strict_types=1);
define('MOSA_READINESS_LIBRARY_ONLY',true);
require dirname(__DIR__).'/scripts/market_collector/runtime_readiness_probe.php';
$input=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);
if(($input['action']??'')==='assess'){
    $calls=[];$fake=static function($command,$stdin)use(&$calls,$input){
        $calls[]=['command'=>$command,'input'=>json_decode($stdin,true)];
        $ok=($input['succeed_at']??99)===count($calls);
        return ['started'=>true,'exit_code'=>0,'result'=>['ok'=>$ok,'executable'=>$command[0]]];
    };
    $r=readinessProbe(['python_source'=>'pass'],$fake);
    echo json_encode(['report'=>$r,'calls'=>$calls],JSON_THROW_ON_ERROR);
}else{
    $flags=['-d','display_errors=0','-d','log_errors=0','-d','auto_prepend_file=','-d','auto_append_file=','-d','opcache.enable_cli=0'];
    $code=match($input['action']??'normal'){
        'stderr'=>'fwrite(STDERR,"synthetic-private-error");',
        'overflow'=>'echo str_repeat("x",40000);',
        default=>'echo json_encode(["marker"=>"harmless"]);'
    };
    echo json_encode(readinessChild([PHP_BINARY,...$flags,'-r',$code],''),JSON_THROW_ON_ERROR);
}
