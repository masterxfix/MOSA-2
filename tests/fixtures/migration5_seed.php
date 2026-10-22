<?php
declare(strict_types=1);
require_once $argv[1].'/scripts/market_current/historical_scope.php';
require __DIR__.'/current_web.php';
$db=new WebCurrentConnection();$out=[];$i=0;
foreach(\Mosa2\ObservationRead\SCOPE as $isin=>$name){
    $q=$db->prepare('SELECT normalized_value');$q->execute([$isin]);$route=$q->fetchAll()[0];
    $q=$db->prepare('SELECT * FROM m2_market_current');$q->execute([(string)(1100+$i)]);$current=$q->fetch();
    $q=$db->prepare('SELECT * FROM m2_market_observations');$q->execute([(string)(9000+$i),(string)(1100+$i)]);$fact=$q->fetch();
    $out[]=['isin'=>$isin,'name'=>$name,'route'=>$route,'current'=>$current,'fact'=>$fact];$i++;
}echo json_encode($out,JSON_THROW_ON_ERROR);
