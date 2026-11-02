<?php
declare(strict_types=1);
namespace Mosa2\TradegateQuote;

use function Mosa2\Phase2\{check,same};
use function Mosa2\MarketIdentity\{matchFields,planAssetIdentity,planMarketRoute};
use function Mosa2\MarketLive\completePlan;
require_once __DIR__.'/live_persistence.php';

const SOURCE_VALUES=[
    'source_key'=>'provider:tradegate_bsx_mid','source_type'=>'market_data',
    'display_name'=>'Tradegate · XGAT · Mid','base_url'=>'https://www.tradegatebsx.com/','enabled'=>'1',
];

/** Pure source decision. The caller allocates any new database ID in its transaction. */
function sourcePlan(array $sources,string $now): array {
    same(\Mosa2\Phase3C\utcTimestamp($now),$now,'tradegate_source_timestamp');
    $rows=array_values(array_filter($sources,static fn($r)=>($r['source_key']??null)===SOURCE_VALUES['source_key']));
    check(count($rows)<=1,'tradegate_source_ambiguous');
    if($rows===[])return ['decision'=>'INSERT','values'=>SOURCE_VALUES+['created_at'=>$now,'updated_at'=>$now]];
    $row=$rows[0];
    check(matchFields($row,SOURCE_VALUES),'tradegate_source_conflict');
    same(\Mosa2\Phase3C\identity($row['id']),$row['id'],'tradegate_source_id');
    foreach(['created_at','updated_at'] as $field)
        same(\Mosa2\Phase3C\utcTimestamp($row[$field]),$row[$field],'tradegate_source_timestamp');
    return ['decision'=>'EXISTING_MATCH','row'=>$row];
}

/** Existing authenticated asset identity plus a distinct, immutable Tradegate Mid route. */
function manifest(array $state,array $selection): array {
    $isin=$selection['isin'];check(\Mosa2\Phase3D\isinValid($isin),'scope_isin');
    $ids=array_values(array_filter($state['m2_asset_identifiers'],static fn($r)=>
        $r['identifier_type']==='isin'&&$r['normalized_value']===$isin&&$r['scope_key']===''));
    same(count($ids),1,'scope_global_identity');$id=$ids[0]['asset_id'];
    $assets=array_values(array_filter($state['m2_assets'],static fn($r)=>$r['entity_id']===$id));
    $entities=array_values(array_filter($state['m2_entities'],static fn($r)=>$r['id']===$id));
    same(count($assets),1,'scope_asset');same(count($entities),1,'scope_entity');
    same($assets[0]['display_name'],$selection['name'],'scope_name');
    $identity=['canonical_name'=>$entities[0]['canonical_name'],'display_name'=>$assets[0]['display_name'],
        'asset_class'=>$assets[0]['asset_class'],'identifier_type'=>'isin','identifier_value'=>$isin,
        'normalized_value'=>$isin,'scope_key'=>'','is_primary'=>1];
    same(planAssetIdentity($state,$identity)['decision'],'EXISTING_MATCH','scope_identity_conflict');

    $sources=array_values(array_filter($state['m2_sources'],static fn($r)=>$r['source_key']===SOURCE_VALUES['source_key']));
    same(count($sources),1,'tradegate_source_required');
    $source=sourcePlan($state['m2_sources'],$sources[0]['updated_at']);
    same($source['decision'],'EXISTING_MATCH','tradegate_source_required');
    $units=array_fill_keys(\Mosa2\MarketIdentity\UNIT_FIELDS,null);
    $units['unit_contract_version']='mosa2-market-unit-v1';$units['quote_unit_key']='EUR';$units['quote_unit_version']='1';
    $evidence=[
        'sample_id'=>'TRADEGATE-'.substr(hash('sha256',$isin),0,10),
        'source_reference'=>'qualified:tradegate:'.$isin,'family'=>'tradegate_quote',
        'row'=>['isin'=>$isin,'provider_key'=>'tradegate_bsx_mid','venue_key'=>'tradegate',
            'currency'=>'EUR','quote_variant'=>'mid','series'=>'snapshot','observation_kind'=>'market_quote'],
        'proof'=>['external_identity'=>['isin'=>$isin,'venue'=>'tradegate'],
            'route_reference'=>'Phase-3D ISIN+venue; TradegateQuoteV1 verifies ISIN/EUR and computes Decimal Bid/Ask Mid',
            'unit_class'=>'currency_per_instrument'],
    ];
    $route=planMarketRoute($state['m2_asset_source_routes'],
        ['asset_id'=>$id,'source_id'=>$source['row']['id'],'route_type'=>'quote','priority'=>0,'enabled'=>$selection['route_enabled']??0,'evidence'=>$evidence],$units);
    check(in_array($route['decision'],['CREATE_REVISION','EXISTING_MATCH'],true),'scope_route_conflict');
    $manifest=['policy'=>$route['decision']==='EXISTING_MATCH'?'USE_EXISTING_ROUTE':'ONBOARD_NEW_ROUTE',
        'identity'=>$identity,'route_evidence'=>$evidence,'unit_binding'=>$units,'instrument'=>$isin,
        'provider_key'=>'tradegate_bsx_quote_v1','adapter_module'=>'scripts.market_collector.tradegate','adapter_class'=>'TradegateQuoteV1'];
    if(isset($selection['route_enabled']))$manifest['route_enabled']=$selection['route_enabled'];
    completePlan($state,$manifest);
    return $manifest;
}
