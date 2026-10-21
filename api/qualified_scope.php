<?php
declare(strict_types=1);
namespace Mosa2\ObservationRead;
use RuntimeException;
require_once __DIR__.'/market_core/selection.php';
const SCOPE=[
    'DE000A0JBPG2'=>'PNE AG','DE0005313704'=>'Carl Zeiss Meditec',
    'AU000000DRO2'=>'DroneShield','CNE100000296'=>'BYD','CNE100006CQ4'=>'Ubtech Robotics'
];
const FIELDS=\Mosa2\QuoteSelection\FIELDS;
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
    checked(isset(SCOPE[$isin])&&$r['isin']===$isin&&$r['asset_status']==='active');
    foreach(['asset_id','source_id','route_id','route_revision'] as $k)checked(is_string($r[$k])&&preg_match('/^[1-9][0-9]*$/D',$r[$k])===1);
    checked($r['source_key']==='provider:boerse_frankfurt_api'&&$r['route_type']==='quote'&&$r['priority']==='0'
        &&in_array($r['enabled'],['0','1'],true)&&$r['external_key']===externalKey($isin));
    $physical=$r+['id'=>$r['route_id']];
    \Mosa2\QuoteSelection\route($physical,\Mosa2\QuoteSelection\catalog());
    checked($r['source_enabled']==='1'&&$r['source_type']==='market_data');
    $unit=\Mosa2\QuoteSelection\unit(\Mosa2\QuoteSelection\catalog(),$r['quote_unit_key'],$r['quote_unit_version']);
    foreach(['status','monetary_currency_code','dimension_key','base_unit_key','base_unit_version','scale_numerator','scale_denominator'] as $i=>$key){
        $column=['unit_status','unit_currency','unit_dimension','unit_base','unit_base_version','unit_scale_numerator','unit_scale_denominator'][$i];
        checked($r[$column]===$unit[$key]);
    }
    return $r;
}
function scopeSql(): string {
    return "SELECT /*+ MAX_EXECUTION_TIME(1500) */ i.normalized_value AS isin,a.entity_id AS asset_id,a.asset_class,a.status AS asset_status,
        s.id AS source_id,s.source_key,s.display_name AS source_name,s.enabled AS source_enabled,s.source_type,r.id AS route_id,r.route_revision,r.route_type,r.external_key,r.priority,r.enabled,
        r.unit_contract_version,r.quote_unit_key,r.quote_unit_version,r.quantity_basis_unit_key,r.quantity_basis_unit_version,r.quantity_basis_amount,r.volume_unit_key,r.volume_unit_version,
        u.status AS unit_status,u.monetary_currency_code AS unit_currency,u.dimension_key AS unit_dimension,u.base_unit_key AS unit_base,u.base_unit_version AS unit_base_version,
        u.scale_numerator AS unit_scale_numerator,u.scale_denominator AS unit_scale_denominator
        FROM m2_asset_identifiers i JOIN m2_assets a ON a.entity_id=i.asset_id
        JOIN m2_sources s ON s.source_key='provider:boerse_frankfurt_api'
        JOIN m2_asset_source_routes r ON r.asset_id=a.entity_id AND r.source_id=s.id AND r.route_type='quote'
        LEFT JOIN m2_units u ON u.unit_key=r.quote_unit_key AND u.unit_version=r.quote_unit_version AND u.unit_contract_version=r.unit_contract_version
        WHERE i.identifier_type='isin' AND i.normalized_value=? AND i.scope_key='' AND i.valid_to IS NULL
        ORDER BY r.route_revision DESC LIMIT 2";
}
