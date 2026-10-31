<?php
declare(strict_types=1);
require dirname(__DIR__).'/scripts/collector_schema4_once.php';
$d=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
try{
    $items=\Mosa2\Schema4Once\selected($d['published'],'five');
    echo json_encode(['ok'=>true,'items'=>$items]);
}catch(Throwable $e){echo json_encode(['ok'=>false,'error'=>$e->getMessage()]);}
