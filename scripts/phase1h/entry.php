<?php
declare(strict_types=1);
const MOSA2_HISTORY_PROFILE='history1000000_v1';
const MOSA2_HISTORY_MILLION=true;
require_once __DIR__.'/million.php';
ini_set('display_errors','0');
ini_set('log_errors','0');
try {
    \Mosa2\Phase1B\ensure(PHP_SAPI==='cli' && ($argv[1]??'')==='--run','explicit_cli_required');
    $private=dirname(__DIR__).'/phase1b';
    $target=require $private.'/target.php';
    $r=\Mosa2\Million\dispatch($target,require $private.'/secret.php',$private,(string)($argv[2]??''));
    echo json_encode($r,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES),PHP_EOL;
    exit(($r['ok']??false)?0:1);
} catch(Throwable $e) {
    echo json_encode(['ok'=>false,'failure'=>$e instanceof \Mosa2\Phase1B\Failure?$e->getMessage():'million_request_failed']),PHP_EOL;exit(1);
}
