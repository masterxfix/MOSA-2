<?php
declare(strict_types=1);
require $argv[1].'/api/observations_read.php';
try {
    $input=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
    $route=$input['route'];$route['route_id']=$route['id'];$route['source_name']='Synthetic source';
    $rows=array_map(static fn($f)=>$f+['dedupe_hex'=>$f['dedupe_key']],$input['facts']);
    $result=\Mosa2\QuoteSelection\select($input['facts'],$input['route'],$input['now'],$input['previous']??null);
    $item=\Mosa2\ObservationRead\latest($rows,$route,$input['isin'],$input['now'],1800);
    echo json_encode(['ok'=>true,'selection'=>$result,'item'=>$item],JSON_THROW_ON_ERROR);
}catch(Throwable $e){echo json_encode(['ok'=>false,'failure'=>$e->getMessage()],JSON_THROW_ON_ERROR);}
