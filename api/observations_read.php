<?php
declare(strict_types=1);
namespace Mosa2\ObservationRead;
use PDO;
use RuntimeException;
use function Mosa2\MarketRead\{present,timestamp};
require_once __DIR__.'/read_model.php';

const SCOPE=[
    'DE000A0JBPG2'=>'PNE AG','DE0005313704'=>'Carl Zeiss Meditec',
    'AU000000DRO2'=>'DroneShield','CNE100000296'=>'BYD','CNE100006CQ4'=>'Ubtech Robotics'
];
const FIELDS=['asset_id','source_id','route_id','currency','market_at','observed_at','price','bid','ask','volume',
    'unit_contract_version','quote_unit_key','quote_unit_version','quantity_basis_unit_key','quantity_basis_unit_version',
    'quantity_basis_amount','volume_unit_key','volume_unit_version'];
function checked(bool $ok): void {if(!$ok)throw new RuntimeException('observation_binding');}
function strings(array $row): array {foreach($row as &$v)if($v!==null)$v=(string)$v;return $row;}
function canonical(array $value): string {
    ksort($value,SORT_STRING);foreach($value as &$v)if(is_array($v))$v=json_decode(canonical($v),true,32,JSON_THROW_ON_ERROR);
    return json_encode($value,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
}
/** Verify the existing Phase-3D ISIN/venue route key; never construct a new route. */
function externalKey(string $isin): string {
    return 'market-v1:'.hash('sha256','route:'.canonical([
        'asset'=>'isin:'.$isin,'provider'=>'boerse_frankfurt_api','venue'=>'boerse_frankfurt','currency'=>'EUR',
        'quote_variant'=>null,'series'=>'snapshot','kind'=>'market_quote',
        'external'=>['isin'=>$isin,'venue'=>'boerse_frankfurt']]));
}
function binding(array $r,string $isin): array {
    checked(isset(SCOPE[$isin])&&$r['isin']===$isin&&$r['asset_class']==='equity'&&$r['asset_status']==='active');
    foreach(['asset_id','source_id','route_id','route_revision'] as $k)checked(is_string($r[$k])&&preg_match('/^[1-9][0-9]*$/D',$r[$k])===1);
    checked($r['source_key']==='provider:boerse_frankfurt_api'&&$r['route_type']==='quote'&&$r['priority']==='0'
        &&in_array($r['enabled'],['0','1'],true)&&$r['external_key']===externalKey($isin));
    checked($r['unit_contract_version']==='mosa2-market-unit-v1'&&$r['quote_unit_key']==='EUR'&&$r['quote_unit_version']==='1');
    foreach(['quantity_basis_unit_key','quantity_basis_unit_version','quantity_basis_amount','volume_unit_key','volume_unit_version'] as $k)checked($r[$k]===null);
    checked($r['unit_status']==='frozen'&&$r['unit_currency']==='EUR'&&$r['unit_dimension']==='monetary'
        &&$r['unit_base']==='EUR'&&$r['unit_base_version']==='1'&&$r['unit_scale_numerator']==='1'&&$r['unit_scale_denominator']==='1');
    return $r;
}
/** Bounded candidate set. The 101st row is a completeness sentinel, not displayed. */
function latest(array $rows,array $route,string $isin,string $now,int $stale): array {
    checked(count($rows)<=101);
    $base=['name'=>SCOPE[$isin],'isin'=>$isin,'source'=>$route['source_name'],'venue'=>'Börse Frankfurt · XFRA'];
    $valid=[];
    foreach(array_slice($rows,0,100) as $raw){
        $r=strings($raw);
        if($r['observation_format_version']===null)continue; // legacy facts are outside the collector-v2 view
        checked($r['observation_format_version']==='2');
        foreach(['asset_id','source_id','route_id'] as $k)checked($r[$k]===$route[$k]);
        foreach(array_slice(FIELDS,10) as $k)checked($r[$k]===$route[$k]);
        checked(preg_match('/^[1-9][0-9]*$/D',$r['id'])===1&&$r['currency']==='EUR'&&$r['volume']===null);
        foreach(['price','bid','ask'] as $k)checked($r[$k]===null&&$k!=='price'||is_string($r[$k])&&preg_match('/^[0-9]+\.[0-9]{10}$/D',$r[$k])===1);
        checked(trim(str_replace('.','',$r['price']),'0')!=='');
        checked($r['bid']===null||$r['ask']===null||strcmp(str_pad($r['bid'],30,'0',STR_PAD_LEFT),str_pad($r['ask'],30,'0',STR_PAD_LEFT))<=0);
        $payload=[];foreach(FIELDS as $k)$payload[$k]=$r[$k];
        checked(is_string($r['dedupe_hex'])&&hash_equals(strtolower($r['dedupe_hex']),hash('sha256',"mosa2-observation-v2\n".json_encode($payload,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR))));
        // Reuse the existing reader's exact-price, timestamp and market-age validation.
        $item=present($r+['display_name'=>SCOPE[$isin],'source_name'=>$route['source_name'],'venue'=>$base['venue'],'valid_binding'=>'1'],$now,$stale);
        checked(timestamp($r['market_at'])<=timestamp($now)); // no future market value advertised
        $valid[]=['row'=>$r,'item'=>$item];
    }
    usort($valid,static function($a,$b){
        foreach(['market_at','observed_at'] as $k){$c=strcmp($b['row'][$k],$a['row'][$k]);if($c)return $c;}
        return strlen($b['row']['id'])<=>strlen($a['row']['id'])?:strcmp($b['row']['id'],$a['row']['id']);
    });
    if(count($rows)===101){
        // ORDER BY market_at,id cannot order observed_at; never hide an unexamined winning tie.
        checked($valid!==[]&&$rows[100]['market_at']<$valid[0]['row']['market_at']);
    }
    if(!$valid)return $base+['status'=>'missing'];
    $winner=$valid[0];$r=$winner['row'];
    foreach($valid as $v)if($v['row']['market_at']===$r['market_at']&&$v['row']['observed_at']===$r['observed_at']){
        // ID is a deterministic tie-breaker, never permission to hide conflicting facts.
        checked($v['row']['dedupe_hex']===$r['dedupe_hex']);
    }
    return $base+$winner['item']+['observation_id'=>$r['id'],
        'age_seconds'=>max(0,timestamp($now)->getTimestamp()-timestamp($r['market_at'])->getTimestamp())];
}
function read(PDO $p,array $config,string $now): array {
    $stale=$config['stale_seconds']??null;checked(is_int($stale)&&$stale>=60&&$stale<=86400);timestamp($now);
    $scope=$p->prepare("SELECT /*+ MAX_EXECUTION_TIME(1500) */ i.normalized_value AS isin,a.entity_id AS asset_id,a.asset_class,a.status AS asset_status,
        s.id AS source_id,s.source_key,s.display_name AS source_name,r.id AS route_id,r.route_revision,r.route_type,r.external_key,r.priority,r.enabled,
        r.unit_contract_version,r.quote_unit_key,r.quote_unit_version,r.quantity_basis_unit_key,r.quantity_basis_unit_version,r.quantity_basis_amount,r.volume_unit_key,r.volume_unit_version,
        u.status AS unit_status,u.monetary_currency_code AS unit_currency,u.dimension_key AS unit_dimension,u.base_unit_key AS unit_base,u.base_unit_version AS unit_base_version,
        u.scale_numerator AS unit_scale_numerator,u.scale_denominator AS unit_scale_denominator
        FROM m2_asset_identifiers i JOIN m2_assets a ON a.entity_id=i.asset_id
        JOIN m2_sources s ON s.source_key='provider:boerse_frankfurt_api'
        JOIN m2_asset_source_routes r ON r.asset_id=a.entity_id AND r.source_id=s.id AND r.route_type='quote'
        LEFT JOIN m2_units u ON u.unit_key=r.quote_unit_key AND u.unit_version=r.quote_unit_version AND u.unit_contract_version=r.unit_contract_version
        WHERE i.identifier_type='isin' AND i.normalized_value=? AND i.scope_key='' AND i.valid_to IS NULL
        ORDER BY r.route_revision DESC LIMIT 2");
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
