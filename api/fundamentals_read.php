<?php
declare(strict_types=1);
namespace Mosa2\FundamentalsRead;

use PDO;
use RuntimeException;

/** Small, bounded reader for stored fundamentals; no writer or provider dependency. */
function checked(bool $ok,string $code='fundamentals_read'): void {
    if(!$ok)throw new RuntimeException($code);
}

function readTransaction(PDO $p,callable $reader): mixed {
    $p->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $p->exec('SET SESSION TRANSACTION READ ONLY');
    checked($p->beginTransaction()&&$p->inTransaction(),'fundamentals_transaction');
    try{
        checked((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn()==='1','fundamentals_transaction');
        return $reader();
    }finally{if($p->inTransaction())$p->rollBack();}
}

function value(array $row): ?string {
    foreach(['value_decimal','value_text','value_date'] as $key)if($row[$key]!==null)return (string)$row[$key];
    return null;
}

function read(PDO $p,?string $isin,string $asOf): array {
    $items=readTransaction($p,static function()use($p,$isin){
        $sql='SELECT a.entity_id AS asset_id,e.canonical_name AS name,i.normalized_value AS isin
            FROM m2_assets a JOIN m2_entities e ON e.id=a.entity_id
            JOIN m2_asset_identifiers i ON i.asset_id=a.entity_id
            WHERE a.asset_class=\'equity\' AND a.status=\'active\' AND e.entity_type=\'asset\' AND e.status=\'active\'
              AND i.identifier_type=\'isin\' AND i.scope_key=\'\' AND i.valid_to IS NULL';
        $args=[];
        if($isin!==null){$sql.=' AND i.normalized_value=?';$args[]=$isin;}
        $sql.=' ORDER BY e.canonical_name,a.entity_id LIMIT 10';
        $assets=$p->prepare($sql);$assets->execute($args);$assets=$assets->fetchAll(PDO::FETCH_ASSOC);
        if ($assets===[]) {
            checked($isin===null,'fundamentals_not_found');
            return [];
        }
        checked(count($assets)<=10,'fundamentals_asset_bound');
        $ids=array_map(static fn($row)=>(string)$row['asset_id'],$assets);
        $marks=implode(',',array_fill(0,count($ids),'?'));
        $facts=$p->prepare('SELECT o.asset_id,o.id AS observation_id,o.metric_key,m.display_name AS metric_name,
                o.value_type,o.dimension_key,o.value_decimal,o.value_text,o.value_date,o.period_type,o.fiscal_year,o.fiscal_quarter,
                o.period_start,o.period_end,o.as_of_at,o.unit_key,o.unit_version,u.display_name AS unit_name,u.monetary_currency_code,
                o.source_id,s.display_name AS source_name,s.base_url AS source_url,o.fetch_id,o.field_path,
                HEX(fi.sha256) AS evidence_sha256,f.observed_at AS captured_at
            FROM m2_fundamental_observations o
            JOIN m2_fundamental_metrics m ON m.metric_key=o.metric_key AND m.value_type=o.value_type AND m.dimension_key=o.dimension_key
            JOIN m2_fundamental_units u ON u.unit_key=o.unit_key AND u.unit_version=o.unit_version
            JOIN m2_provider_fetches f ON f.id=o.fetch_id AND f.source_id=o.source_id
            JOIN m2_files fi ON fi.id=f.file_id
            JOIN m2_sources s ON s.id=o.source_id
            WHERE o.asset_id IN ('.$marks.')
            ORDER BY o.asset_id,o.metric_key,o.period_type,o.fiscal_year,o.fiscal_quarter,o.period_end,o.as_of_at,o.id
            LIMIT 2304');
        $facts->execute($ids);$facts=$facts->fetchAll(PDO::FETCH_ASSOC);
        checked(count($facts)<=2304,'fundamentals_fact_bound');
        $current=$p->prepare('SELECT asset_id,metric_key,period_type,fiscal_year,fiscal_quarter,period_start,period_end,as_of_at,
                observation_id,source_id,value_type,dimension_key,unit_key,unit_version,value_decimal,value_text,value_date,updated_at
            FROM m2_fundamental_current WHERE asset_id IN ('.$marks.')
            ORDER BY asset_id,metric_key,period_type LIMIT 2304');
        $current->execute($ids);$current=$current->fetchAll(PDO::FETCH_ASSOC);
        checked(count($current)<=2304,'fundamentals_current_bound');
        $byAsset=[];$byObservation=[];
        foreach($facts as $row){
            $asset=(string)$row['asset_id'];$observation=(string)$row['observation_id'];
            $byObservation[$asset][$observation]=$row;
            $byAsset[$asset][]=$row;
        }
        $currentByObservation=[];$currentItems=[];
        foreach($current as $row){
            $asset=(string)$row['asset_id'];$observation=(string)$row['observation_id'];$fact=$byObservation[$asset][$observation]??null;
            checked($fact!==null,'fundamentals_current_reference');
            foreach(['metric_key','period_type','source_id','unit_key','unit_version','value_type','dimension_key'] as $key)
                checked((string)$row[$key]===(string)$fact[$key],'fundamentals_current_binding');
            foreach(['fiscal_year','fiscal_quarter','period_start','period_end','as_of_at'] as $key)
                checked(($row[$key]??null)===($fact[$key]??null),'fundamentals_current_period');
            checked(value($row)===value($fact),'fundamentals_current_value');
            $currentByObservation[$asset][$observation]=true;
            $currentItems[$asset][]=array(
                'metric_key'=>(string)$row['metric_key'],'period_type'=>(string)$row['period_type'],
                'fiscal_year'=>$row['fiscal_year']===null?null:(string)$row['fiscal_year'],
                'fiscal_quarter'=>$row['fiscal_quarter']===null?null:(string)$row['fiscal_quarter'],
                'period_start'=>$row['period_start'],'period_end'=>$row['period_end'],'as_of_at'=>$row['as_of_at']??null,
                'observation_id'=>$observation,'value'=>value($row),'unit_key'=>(string)$row['unit_key'],
                'unit_version'=>(string)$row['unit_version'],'updated_at'=>(string)$row['updated_at'].'Z');
        }
        $out=[];
        foreach($assets as $asset){
            $assetId=(string)$asset['asset_id'];$observations=[];
            foreach($byAsset[$assetId]??[] as $row){
                $observations[]=array(
                    'observation_id'=>(string)$row['observation_id'],'metric_key'=>(string)$row['metric_key'],
                    'metric_name'=>(string)$row['metric_name'],'value_type'=>(string)$row['value_type'],
                    'value'=>value($row),'period_type'=>(string)$row['period_type'],
                    'fiscal_year'=>$row['fiscal_year']===null?null:(string)$row['fiscal_year'],
                    'fiscal_quarter'=>$row['fiscal_quarter']===null?null:(string)$row['fiscal_quarter'],
                    'period_start'=>$row['period_start'],'period_end'=>$row['period_end'],'as_of_at'=>$row['as_of_at']??null,
                    'unit_key'=>(string)$row['unit_key'],'unit_name'=>(string)$row['unit_name'],
                    'currency'=>$row['monetary_currency_code']===null?null:(string)$row['monetary_currency_code'],
                    'source'=>(string)$row['source_name'],'source_url'=>$row['source_url']===null?null:(string)$row['source_url'],
                    'captured_at'=>(string)$row['captured_at'].'Z','fetch_id'=>(string)$row['fetch_id'],
                    'field_path'=>(string)$row['field_path'],'evidence_sha256'=>strtolower((string)$row['evidence_sha256']),
                    'current'=>isset($currentByObservation[$assetId][(string)$row['observation_id']])) ;
            }
            $out[]=array('name'=>(string)$asset['name'],'isin'=>(string)$asset['isin'],
                'observations'=>$observations,'current'=>$currentItems[$assetId]??[]);
        }
        return $out;
    });
    $observationCount=0;$currentCount=0;foreach($items as $item){$observationCount+=count($item['observations']);$currentCount+=count($item['current']);}
    return array('status'=>'ok','as_of'=>$asOf.'Z','totals'=>array('assets'=>count($items),
        'fundamental_observations'=>$observationCount,'fundamental_current'=>$currentCount),'items'=>$items);
}
