<?php
declare(strict_types=1);
namespace Mosa2\QuoteSelection;
use function Mosa2\MarketCore\{identity,decimal,utcTimestamp,compareDecimal,requireValue};
require_once __DIR__.'/values.php';
const CORE=['asset_id','source_id','route_id','currency','market_at','observed_at','price','bid','ask','volume'];
const UNITS=['unit_contract_version','quote_unit_key','quote_unit_version','quantity_basis_unit_key',
    'quantity_basis_unit_version','quantity_basis_amount','volume_unit_key','volume_unit_version'];
const FIELDS=[...CORE,...UNITS];

/** Same pinned, frozen catalog used by the existing v2 writer. No database I/O. */
function catalog(): array {
    $wire=file_get_contents(__DIR__.'/units.json');
    requireValue(hash('sha256',$wire)==='0d9f196e4ccbd5e687292fa3d7a1a087b343ec81fb609b8b64b6454713246bbf','quote_catalog');
    return json_decode($wire,true,32,JSON_THROW_ON_ERROR)['definitions'];
}
function unit(array $catalog,mixed $key,mixed $version): array {
    requireValue(is_string($key)&&preg_match('/^[A-Z][A-Z0-9_]{0,63}$/D',$key)===1,'quote_unit');
    requireValue(is_string($version)&&identity($version)===$version&&compareDecimal($version,'4294967295')<=0,'quote_unit_version');
    foreach($catalog as $u)if($u['unit_key']===$key&&$u['unit_version']===$version){
        requireValue($u['status']==='frozen'&&$u['unit_contract_version']==='mosa2-market-unit-v1','quote_unit_status');return $u;
    }
    throw new \InvalidArgumentException('quote_unknown_unit');
}
function route(array $r,array $catalog): void {
    foreach(['id','asset_id','source_id','route_revision','route_type','priority','enabled',...UNITS] as $k)
        requireValue(array_key_exists($k,$r),'quote_route_fields');
    foreach(['id','asset_id','source_id','route_revision'] as $k)requireValue(identity($r[$k])===$r[$k],'quote_route_identity');
    requireValue(compareDecimal($r['route_revision'],'4294967295')<=0,'quote_route_revision');
    requireValue($r['route_type']==='quote'&&$r['priority']==='0'&&in_array($r['enabled'],['0','1'],true),'quote_route');
    requireValue($r['unit_contract_version']==='mosa2-market-unit-v1','quote_unit_contract');
    unit($catalog,$r['quote_unit_key'],$r['quote_unit_version']);
    $triple=array_map(static fn($k)=>$r[$k],array_slice(UNITS,3,3));
    requireValue($triple===[null,null,null]||!in_array(null,$triple,true),'quote_quantity_triple');
    if($triple[0]!==null){
        unit($catalog,$triple[0],$triple[1]);
        requireValue(is_string($triple[2])&&preg_match('/^(0|[1-9][0-9]*)\.[0-9]{8}$/D',$triple[2])===1
            &&decimal($triple[2],32,8)===$triple[2]&&compareDecimal($triple[2],'0.00000000')>0,'quote_quantity');
    }
    requireValue(($r['volume_unit_key']===null)===($r['volume_unit_version']===null),'quote_volume_pair');
    if($r['volume_unit_key']!==null)unit($catalog,$r['volume_unit_key'],$r['volume_unit_version']);
}
function clock(array $row,string $now): void {
    foreach(['market_at','observed_at'] as $k)requireValue(utcTimestamp($row[$k])===$row[$k],'quote_timestamp');
    requireValue(utcTimestamp($now)===$now,'quote_clock');
    $limit=(new \DateTimeImmutable($now,new \DateTimeZone('UTC')))->modify('+5 minutes')->format('Y-m-d H:i:s.u');
    requireValue($row['market_at']<=$row['observed_at']&&$row['market_at']<=$now&&$row['observed_at']<=$limit,'quote_clock');
}
function age(array $row,string $now): int {
    clock($row,$now);
    return max(0,(new \DateTimeImmutable($now,new \DateTimeZone('UTC')))->getTimestamp()
        -(new \DateTimeImmutable($row['market_at'],new \DateTimeZone('UTC')))->getTimestamp());
}
/** Native v2 only. Invalid v2 facts fail closed; legacy facts are excluded by callers. */
function qualified(array $fact,array $r,array $catalog,string $now): array {
    foreach([...FIELDS,'id','observation_format_version','dedupe_key'] as $k)
        requireValue(array_key_exists($k,$fact),'quote_fact_fields');
    requireValue(identity($fact['id'])===$fact['id'],'quote_fact_identity');
    requireValue($fact['observation_format_version']==='2','quote_requires_native_v2');
    $payload=[];foreach(FIELDS as $k)$payload[$k]=$fact[$k];
    $normalized=\Mosa2\Phase3N\values($payload);
    foreach(CORE as $k)requireValue($normalized[$k]===$payload[$k],'quote_noncanonical_fact');
    foreach(['asset_id','source_id'] as $k)requireValue($payload[$k]===$r[$k],'quote_identity_binding');
    requireValue($payload['route_id']===$r['id'],'quote_route_binding');
    foreach(UNITS as $k)requireValue($payload[$k]===$r[$k],'quote_unit_binding');
    requireValue($payload['currency']===unit($catalog,$payload['quote_unit_key'],$payload['quote_unit_version'])['monetary_currency_code'],'quote_currency');
    requireValue(($payload['volume']===null)===($payload['volume_unit_key']===null),'quote_volume');
    $key=$fact['dedupe_key'];
    requireValue(is_string($key)&&preg_match('/^[a-fA-F0-9]{64}$/D',$key)===1,'quote_dedupe');
    $hash=hash('sha256',"mosa2-observation-v2\n".json_encode($payload,JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
    requireValue(hash_equals($hash,strtolower($key)),'quote_dedupe');
    clock($payload,$now);
    return $payload+['id'=>$fact['id'],'observation_format_version'=>'2','dedupe_key'=>strtoupper($key)];
}
function order(array $a,array $b): int {
    return strcmp($a['market_at'],$b['market_at'])?:strcmp($a['observed_at'],$b['observed_at']);
}
/** One generic decision contract for the existing Current planner and Observations. */
function select(array $facts,array $r,string $now,?array $previous=null,?array $units=null): array {
    $units??=catalog();route($r,$units);requireValue(utcTimestamp($now)===$now,'quote_clock');
    $checked=[];$times=[];$ids=[];
    foreach([...$facts,...($previous===null?[]:[$previous])] as $fact){
        $v=qualified($fact,$r,$units,$now);$time=$v['market_at'].'/'.$v['observed_at'];
        requireValue(!isset($times[$time])||$times[$time]===$v['dedupe_key'],'current_equal_time_conflict');
        requireValue(!isset($ids[$v['id']])||$ids[$v['id']]===$v['dedupe_key'],'quote_id_conflict');
        $times[$time]=$v['dedupe_key'];$ids[$v['id']]=$v['dedupe_key'];$checked[]=$v;
    }
    if($previous!==null)array_pop($checked);
    usort($checked,static fn($a,$b)=>-order($a,$b)?:strlen($b['id'])<=>strlen($a['id'])?:strcmp($b['id'],$a['id']));
    $winner=$checked[0]??null;
    if($winner===null)return ['decision'=>$previous===null?'MISSING':'UNCHANGED','fact'=>$previous];
    if($previous!==null){
        $comparison=order($winner,$previous);
        if($comparison<=0)return ['decision'=>$comparison<0?'UNCHANGED_OLDER':'UNCHANGED','fact'=>$previous];
    }
    return ['decision'=>$previous===null?'INSERT':'UPDATE','fact'=>$winner];
}
