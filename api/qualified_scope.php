<?php
declare(strict_types=1);
namespace Mosa2\ObservationRead;
use RuntimeException;
require_once __DIR__.'/market_core/selection.php';
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
function binding(array $r,string $isin,bool $published=false): array {
    checked(preg_match('/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/D',$isin)===1&&$r['isin']===$isin&&$r['asset_status']==='active');
    foreach(['asset_id','source_id','route_id','route_revision'] as $k)checked(is_string($r[$k])&&preg_match('/^[1-9][0-9]*$/D',$r[$k])===1);
    checked($r['route_type']==='quote'&&$r['priority']==='0'&&in_array($r['enabled'],['0','1'],true));
    if(!$published||$r['source_key']==='provider:boerse_frankfurt_api')
        checked($r['source_key']==='provider:boerse_frankfurt_api'&&$r['external_key']===externalKey($isin));
    else checked(preg_match('/^provider:[a-z0-9_]+$/D',$r['source_key'])===1
        &&preg_match('/^market-v1:[a-f0-9]{64}$/D',$r['external_key'])===1);
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

/** Publication starts only from an explicitly projected Current row, never the registry. */
function publishedSql(): string {
    $sql=scopeSql();
    $select=substr($sql,0,strpos($sql,'FROM m2_asset_identifiers'));
    $select=str_replace('a.asset_class,','a.asset_class,a.display_name,e.status AS entity_status,',$select);
    return $select."FROM m2_market_current c
        LEFT JOIN m2_assets a ON a.entity_id=c.asset_id
        LEFT JOIN m2_entities e ON e.id=a.entity_id AND e.entity_type='asset'
        LEFT JOIN m2_asset_identifiers i ON i.asset_id=a.entity_id AND i.identifier_type='isin' AND i.scope_key='' AND i.is_primary=1 AND i.valid_to IS NULL
        LEFT JOIN m2_sources s ON s.id=c.source_id
        LEFT JOIN m2_asset_source_routes r ON r.id=c.route_id AND r.asset_id=c.asset_id AND r.source_id=c.source_id
        LEFT JOIN m2_units u ON u.unit_key=r.quote_unit_key AND u.unit_version=r.quote_unit_version AND u.unit_contract_version=r.unit_contract_version
        ORDER BY c.asset_id LIMIT 11";
}
function readTransaction(\PDO $p,callable $reader): mixed {
    $p->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $p->exec('SET SESSION TRANSACTION READ ONLY');checked($p->beginTransaction()&&$p->inTransaction());
    try {
        checked((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn()==='1');
        return $reader();
    }finally{if($p->inTransaction())$p->rollBack();}
}
