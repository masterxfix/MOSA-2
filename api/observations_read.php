<?php
declare(strict_types=1);
namespace Mosa2\ObservationRead;
use PDO;
use RuntimeException;
use function Mosa2\MarketRead\{present,timestamp};
require_once __DIR__.'/read_model.php';

require_once __DIR__.'/qualified_scope.php';
/** Bounded candidate set. The 101st row is a completeness sentinel, not displayed. */
function latest(array $rows,array $route,string $isin,string $now,int $stale): array {
    checked(count($rows)<=101);
    $base=['name'=>SCOPE[$isin],'isin'=>$isin,'source'=>$route['source_name'],'venue'=>'Börse Frankfurt · XFRA'];
    $facts=[];
    foreach(array_slice($rows,0,100) as $raw){
        $r=strings($raw);
        if($r['observation_format_version']===null)continue;
        $r['dedupe_key']=$r['dedupe_hex'];$facts[]=$r;
    }
    $selection=\Mosa2\QuoteSelection\select($facts,$route+['id'=>$route['route_id']],$now);
    $r=$selection['fact'];
    if(count($rows)===101){
        // The sentinel must be strictly older; never hide an unexamined tie.
        checked($r!==null&&$rows[100]['market_at']<$r['market_at']);
    }
    if($r===null)return $base+['status'=>'missing'];
    $item=present($r+['display_name'=>$base['name'],'source_name'=>$route['source_name'],'venue'=>$base['venue'],'valid_binding'=>'1'],$now,$stale);
    return $base+$item+['observation_id'=>$r['id'],'age_seconds'=>\Mosa2\QuoteSelection\age($r,$now)];
}

function read(PDO $p,array $config,string $now): array {
    $stale=$config['stale_seconds']??null;checked(is_int($stale)&&$stale>=60&&$stale<=86400);timestamp($now);
    $scope=$p->prepare(scopeSql());
    $facts=$p->prepare('SELECT /*+ MAX_EXECUTION_TIME(1500) */ id,'.implode(',',FIELDS).',observation_format_version,HEX(dedupe_key) AS dedupe_hex
        FROM m2_market_observations WHERE asset_id=? AND source_id=? ORDER BY market_at DESC,id DESC LIMIT 101');
    $items=[];$p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
    try{
        foreach(SCOPE as $isin=>$name){
            $scope->execute([$isin]);$routes=$scope->fetchAll(PDO::FETCH_ASSOC);checked(count($routes)>=1&&count($routes)<=2);
            $r=binding(strings($routes[0]),$isin);
            if(count($routes)===2)checked((int)$routes[1]['route_revision']<(int)$r['route_revision']);
            $facts->execute([$r['asset_id'],$r['source_id']]);$rows=$facts->fetchAll(PDO::FETCH_ASSOC);
            $items[]=latest($rows,$r,$isin,$now,$stale);
        }
    }finally{if($p->inTransaction())$p->rollBack();}
    return ['status'=>'ok','as_of'=>$now.'Z','stale_seconds'=>$stale,'items'=>$items];
}
