<?php
declare(strict_types=1);
namespace Mosa2\MarketRead;
use PDO;
use DateTimeImmutable;
use DateTimeZone;
use RuntimeException;

/** No write capability, provider dependency or caller-controlled SQL. */
function timestamp(string $value): DateTimeImmutable {
    $date=DateTimeImmutable::createFromFormat('!Y-m-d H:i:s.u',$value,new DateTimeZone('UTC'));
    if(!$date||$date->format('Y-m-d H:i:s.u')!==$value)throw new RuntimeException('market_timestamp');return $date;
}
function present(array $row,string $now,int $staleSeconds): array {
    $base=['name'=>$row['display_name'],'source'=>$row['source_name'],'venue'=>$row['venue']];
    if($row['price']===null)return $base+['status'=>'missing'];
    if($row['valid_binding']!=='1'||!is_string($row['price'])||!preg_match('/^-?[0-9]+\.[0-9]{10}$/D',$row['price']))throw new RuntimeException('market_binding');
    $market=timestamp($row['market_at']);$observed=timestamp($row['observed_at']);$clock=timestamp($now);
    if($market>$observed||$observed>$clock->modify('+5 minutes'))throw new RuntimeException('market_clock');
    return $base+['status'=>$clock->getTimestamp()-$market->getTimestamp()>$staleSeconds?'stale':'stored',
        'price'=>$row['price'],'unit'=>$row['quote_unit_key'],'unit_version'=>$row['quote_unit_version'],
        'currency'=>$row['currency'],'quantity_basis_unit'=>$row['quantity_basis_unit_key'],
        'quantity_basis_amount'=>$row['quantity_basis_amount'],'market_at'=>$row['market_at'].'Z','observed_at'=>$row['observed_at'].'Z'];
}
function read(PDO $p,array $config,string $now): array {
    $assets=$config['assets'];if(count($assets)<1||count($assets)>10)throw new RuntimeException('market_scope');
    $stale=$config['stale_seconds'];if(!is_int($stale)||$stale<60||$stale>86400)throw new RuntimeException('market_age_policy');
    $sql='SELECT a.display_name,s.display_name AS source_name,c.price,c.currency,c.quote_unit_key,c.quote_unit_version,c.quantity_basis_unit_key,c.quantity_basis_amount,c.market_at,c.observed_at,
        (c.observation_id IS NOT NULL AND c.observation_format_version=2 AND c.observation_dedupe_key IS NOT NULL AND c.route_id=r.id AND c.route_revision=r.route_revision AND c.source_id=r.source_id AND c.unit_contract_version=r.unit_contract_version AND c.quote_unit_key=r.quote_unit_key AND c.quote_unit_version=r.quote_unit_version AND c.quantity_basis_unit_key<=>r.quantity_basis_unit_key AND c.quantity_basis_unit_version<=>r.quantity_basis_unit_version AND c.quantity_basis_amount<=>r.quantity_basis_amount AND u.status=\'frozen\' AND u.monetary_currency_code<=>c.currency) AS valid_binding
        FROM m2_assets a JOIN m2_asset_source_routes r ON r.asset_id=a.entity_id AND r.id=? JOIN m2_sources s ON s.id=r.source_id LEFT JOIN m2_market_current c ON c.asset_id=a.entity_id LEFT JOIN m2_units u ON u.unit_key=c.quote_unit_key AND u.unit_version=c.quote_unit_version WHERE a.entity_id=? LIMIT 1';
    $q=$p->prepare($sql);$items=[];$seen=[];$p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
    try{foreach($assets as $asset){
        foreach(['asset_id','route_id'] as $key)if(!is_string($asset[$key])||!preg_match('/^[1-9][0-9]*$/D',$asset[$key]))throw new RuntimeException('market_identity');
        if(isset($seen[$asset['asset_id']]))throw new RuntimeException('market_duplicate_scope');$seen[$asset['asset_id']]=true;
        $q->execute([$asset['route_id'],$asset['asset_id']]);$row=$q->fetch(PDO::FETCH_ASSOC);if($row===false)throw new RuntimeException('market_asset_missing');
        foreach($row as &$value)if($value!==null)$value=(string)$value;unset($value);$row['venue']=$asset['venue'];$items[]=present($row,$now,$stale);
    }}finally{if($p->inTransaction())$p->rollBack();}
    return ['status'=>'ok','as_of'=>$now.'Z','stale_seconds'=>$stale,'items'=>$items];
}
