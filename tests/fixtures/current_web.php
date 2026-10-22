<?php
declare(strict_types=1);
require $argv[1].'/api/current_read.php';
$source=file_get_contents($argv[1].'/tests/fixtures/observation_read.php');
$source=substr($source,5,strpos($source,'$db=new ObservationConnection')-5);
$source=str_replace('require $argv','require_once $argv',$source);eval($source);
require_once __DIR__.'/market_read_fakes.php';
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    $db=new WebCurrentConnection($argv[2]??'valid');
    try{$reply=\Mosa2\MarketRead\read($db,['assets'=>[['asset_id'=>'old','route_id'=>'old']],'stale_seconds'=>1800],NOW);}
    catch(Throwable){$reply=['status'=>'error'];}
    echo json_encode($reply+['events'=>$db->events,'sql'=>$db->sql,'parameters'=>$db->parameters],JSON_THROW_ON_ERROR);
}
