<?php
declare(strict_types=1);
namespace Mosa2\Phase3M;
require_once __DIR__.'/live_seed.php';
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    ini_set('display_errors','0');ini_set('log_errors','0');$password=null;
    try {
        $classification=json_decode(file_get_contents(__DIR__.'/diagnosis.json'),true,512,JSON_THROW_ON_ERROR);
        \Mosa2\Phase2\check(in_array($classification['classification'],['METADATA_ONLY_DRIFT','CHECKER_BASELINE_BUG'],true),'worker_classification');
        $password=stream_get_contents(STDIN,1025);\Mosa2\Phase2\check(strlen($password)>0&&strlen($password)<=1024,'worker_password');
        echo json_encode(run(__DIR__,$password),JSON_THROW_ON_ERROR);
    }finally{unset($password);}
}
