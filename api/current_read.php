<?php
declare(strict_types=1);
namespace Mosa2\CurrentRead;
use PDO;
use RuntimeException;
use function Mosa2\ObservationRead\{checked,strings,binding,scopeSql};
require_once __DIR__.'/read_model.php';
require_once __DIR__.'/qualified_scope.php';

/** Current is the only display source. The referenced fact only verifies provenance. */
function item(?array $current,?array $origin,array $r,string $isin,string $now,int $stale): array {
    $base=['name'=>\Mosa2\ObservationRead\SCOPE[$isin],'source'=>$r['source_name'],'venue'=>'Börse Frankfurt · XFRA'];
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
function read(PDO $p,array $config,string $now): array {
    $stale=$config['stale_seconds']??null;checked(is_int($stale)&&$stale>=60&&$stale<=86400);
    \Mosa2\MarketRead\timestamp($now);
    $p->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $p->exec('SET SESSION TRANSACTION READ ONLY');checked($p->beginTransaction()&&$p->inTransaction());
    try{
        checked((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn()==='1');
        $scope=$p->prepare(scopeSql());
        $current=$p->prepare('SELECT *,HEX(observation_dedupe_key) AS observation_dedupe_key FROM m2_market_current WHERE asset_id=? LIMIT 1');
        $fact=$p->prepare('SELECT id,'.implode(',',\Mosa2\QuoteSelection\FIELDS).',observation_format_version,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE id=? AND asset_id=? AND source_id=? AND route_id=? LIMIT 1');
        $items=[];$seen=[];
        foreach(\Mosa2\ObservationRead\SCOPE as $isin=>$name){
            $scope->execute([$isin]);$routes=$scope->fetchAll(PDO::FETCH_ASSOC);checked(count($routes)>=1&&count($routes)<=2);
            $r=binding(strings($routes[0]),$isin);
            if(count($routes)===2)checked((int)$routes[1]['route_revision']<(int)$r['route_revision']);
            checked(!isset($seen[$r['asset_id']]));$seen[$r['asset_id']]=true;
            $current->execute([$r['asset_id']]);$row=$current->fetch(PDO::FETCH_ASSOC);$origin=null;
            if($row!==false){
                $row=strings($row);
                foreach(['asset_id','source_id'] as $k)checked($row[$k]===$r[$k]);
                checked($row['route_id']===$r['route_id']);
                $fact->execute([$row['observation_id'],$r['asset_id'],$r['source_id'],$r['route_id']]);
                $origin=$fact->fetch(PDO::FETCH_ASSOC);checked($origin!==false);
            }
            $items[]=item($row===false?null:$row,$origin,$r,$isin,$now,$stale);
        }
    }finally{if($p->inTransaction())$p->rollBack();}
    return ['status'=>'ok','as_of'=>$now.'Z','stale_seconds'=>$stale,'items'=>$items];
}
