<?php
declare(strict_types=1);
namespace Mosa2\CurrentRead;
use PDO;
use RuntimeException;
use function Mosa2\ObservationRead\{checked,strings,binding,publishedSql,readTransaction};
require_once __DIR__.'/read_model.php';
require_once __DIR__.'/qualified_scope.php';

/** Current is the only display source. The referenced fact only verifies provenance. */
function item(?array $current,?array $origin,array $r,string $isin,string $now,int $stale): array {
    $base=['name'=>$r['display_name'],'source'=>$r['source_name'],'venue'=>$r['source_key']==='provider:boerse_frankfurt_api'?'Börse Frankfurt · XFRA':'—'];
    if($current===null)return $base+['status'=>'missing'];
    checked($origin!==null);
    $current=strings($current);$origin=strings($origin);
    $qualified=\Mosa2\QuoteSelection\qualified($origin,$r+['id'=>$r['route_id']],\Mosa2\QuoteSelection\catalog(),$now);
    foreach(array_intersect_key($qualified,$current) as $k=>$v)checked($current[$k]===$v);
    checked($current['observation_id']===$origin['id']&&$current['observation_format_version']==='2'
        &&$current['route_revision']===$r['route_revision']
        &&hash_equals($qualified['dedupe_key'],strtoupper($current['observation_dedupe_key'])));
    return \Mosa2\MarketRead\present($current+['display_name'=>$base['name'],'source_name'=>$base['source'],'venue'=>$base['venue'],'valid_binding'=>'1'],$now,$stale);
}
/** The same validated publication boundary is used by both web views. */
function published(PDO $p,string $now,int $stale): array {
    $scope=$p->prepare(publishedSql());$scope->execute([]);$routes=$scope->fetchAll(PDO::FETCH_ASSOC);
    checked(count($routes)<=10);
    $current=$p->prepare('SELECT *,HEX(observation_dedupe_key) AS observation_dedupe_key FROM m2_market_current WHERE asset_id=? LIMIT 1');
    $fact=$p->prepare('SELECT id,'.implode(',',\Mosa2\QuoteSelection\FIELDS).',observation_format_version,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE id=? AND asset_id=? AND source_id=? AND route_id=? LIMIT 1');
    $items=[];$seen=[];
    foreach($routes as $raw){
        $r=strings($raw);checked(is_string($r['isin'])&&$r['entity_status']==='active'
            &&is_string($r['display_name'])&&trim($r['display_name'])!==''&&strlen($r['display_name'])<=255);
        $r=binding($r,$r['isin'],true);checked(!isset($seen[$r['asset_id']]));$seen[$r['asset_id']]=true;
        $current->execute([$r['asset_id']]);$row=$current->fetch(PDO::FETCH_ASSOC);checked($row!==false);$row=strings($row);
        foreach(['asset_id','source_id','route_id'] as $k)checked($row[$k]===$r[$k]);
        $fact->execute([$row['observation_id'],$r['asset_id'],$r['source_id'],$r['route_id']]);
        $origin=$fact->fetch(PDO::FETCH_ASSOC);checked($origin!==false);
        $items[]=['route'=>$r,'item'=>item($row,$origin,$r,$r['isin'],$now,$stale)];
    }
    return $items;
}
function read(PDO $p,array $config,string $now): array {
    $stale=$config['stale_seconds']??null;checked(is_int($stale)&&$stale>=60&&$stale<=86400);
    \Mosa2\MarketRead\timestamp($now);
    $items=readTransaction($p,static fn()=>array_column(published($p,$now,$stale),'item'));
    return ['status'=>'ok','as_of'=>$now.'Z','stale_seconds'=>$stale,'items'=>$items];
}
