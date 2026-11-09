<?php
declare(strict_types=1);
namespace Mosa2\Fundamentals;
use function Mosa2\Phase2\{check,same};

/** Curated provenance is an input-manifest receipt, never an HTTP-response receipt. */
function curatedEvidence(array $plan,array $doc): void {
    $meta=$plan['metadata'];$method='manually_reviewed_public_facts';
    same($doc['format'],'mosa2-curated-evidence-v1','curated_format');same($doc['kind'],'curated_evidence','curated_kind');
    same($doc['input_method'],$method,'curated_method');same($meta['input_method'],$method,'curated_method');
    same($meta['payload_kind'],'curated_manifest','curated_payload_kind');same($meta['http_status'],null,'curated_http');
    same($meta['content_type'],'application/json','curated_content_type');
    same($doc['http_request_performed'],false,'curated_http');same($doc['http_response'],null,'curated_response');
    check(!isset($meta['request_started_at']),'curated_no_request_time');
    same(canonical($doc['input_manifest']),canonical($meta),'curated_input_binding');
    $raw=$doc['manifest_json'];check(is_string($raw)&&strlen($raw)<=65536,'curated_input_bound');
    same(strlen($raw),$meta['bytes'],'curated_input_bytes');same(hash('sha256',$raw),$meta['sha256'],'curated_input_hash');
    $manifest=json_decode($raw,true,64,JSON_THROW_ON_ERROR);
    $primary=$manifest['format']==='mosa2-curated-facts-v2';
    same($manifest['format'],$primary?'mosa2-curated-facts-v2':'mosa2-curated-facts-v1','curated_manifest_format');same($manifest['input_method'],$method,'curated_manifest_method');
    same($plan['parser_key'],'curated_public_facts_v1','curated_parser');same($plan['parser_version'],$primary?'2':'1','curated_parser_version');
    same($plan['publish_current']??true,$primary?($manifest['publish_current']??true):true,'curated_projection');
    check(is_bool($plan['publish_current']??true),'curated_projection');
    same($plan['source']['source_type'],$method,'curated_source_type');same($plan['source']['enabled'],'0','curated_source_disabled');
    same(canonical($manifest['source']),canonical($plan['source']),'curated_source');
    foreach(['metrics','units','fiscal_year_start_month'] as $k)same(canonical($manifest[$k]),canonical($plan[$k]),'curated_catalog');
    same($doc['source_url'],$manifest['primary_url'],'curated_url');same($meta['url'],$manifest['primary_url'],'curated_url');
    check(str_starts_with($meta['url'],$plan['source']['base_url']),'curated_source_base');
    same($doc['source_classification'],$primary?'issuer_primary_document':'independent_third_party_report_reproduction','curated_classification');
    same($manifest['source_classification'],$doc['source_classification'],'curated_classification');
    same(canonical($doc['issuer']),canonical($manifest['issuer']),'curated_issuer');
    same(canonical($doc['research']),canonical($manifest['research']),'curated_research');
    same(canonical($doc['comparison_sources']),canonical($manifest['comparison_sources']),'curated_comparison');
    same($doc['research']['review_status'],$primary?'primary_document_manually_verified':'user_attested_manually_reviewed','curated_review');
    same($doc['research']['independently_refetched_by_runner'],false,'curated_review');
    $research=$doc['research']['researched_at'];timestamp($research);timestamp($meta['observed_at']);
    same($doc['research']['time_status'],$research===null?'before_assignment_exact_time_unknown':'known_utc','curated_research_time');
    check($research===null||$research<=$meta['observed_at'],'curated_research_time');
    same($doc['imported_at'],$meta['observed_at'],'curated_import_time');
    same(count($manifest['facts']),count($plan['observations']),'curated_fact_count');
    same(count($doc['facts']),count($plan['observations']),'curated_evidence_count');
    foreach($plan['observations'] as $i=>$row){$original=$manifest['facts'][$i];$fact=$doc['facts'][$i];
        same($original['metric_key'],$row['metric_key'],'curated_metric');same($original['unit_key'],$row['unit_key'],'curated_unit');
        same($original['validation_status'],'manually_reviewed','curated_review');
        check($primary?is_bool($original['rounded']):$original['rounded']===true,'curated_rounded');
        check(is_int($original['decimal_places'])&&$original['decimal_places']>=0&&$original['decimal_places']<=12,'curated_precision');
        $parts=explode('.',$original['value']);same(strlen($parts[1]??''),$original['decimal_places'],'curated_precision');
        same(decimal($original['value']),decimal($row['value_decimal']),'curated_value');
        $period=$manifest['periods'][$original['period']];
        foreach($period as $k=>$v)same($row[$k],$v,'curated_period');
        same($row['observed_at'],$meta['observed_at'],'curated_observed');same($row['reported_at'],null,'curated_publication');
        same($row['as_of_at'],$primary?($period['as_of_at']??null):null,'curated_asof');
        if($row['period_type']==='snapshot')check($primary&&str_ends_with($row['as_of_at'],' 00:00:00.000000'),'curated_snapshot_date');
        if(($plan['publish_current']??true)===false)same($row['period_type'],'snapshot','curated_history_only');
        foreach(['original_label','original_unit','section','column'] as $k)check(is_string($original[$k])&&strlen($original[$k])>0&&strlen($original[$k])<=255,'curated_reference');
        $unit=array_values(array_filter($plan['units'],fn($u)=>$u['unit_key']===$row['unit_key']));same(count($unit),1,'curated_unit');
        same($original['original_unit'],$unit[0]['display_name'],'curated_original_unit');
        check($row['dimension_key']==='monetary'||($primary&&$row['dimension_key']==='share_count'&&$original['decimal_places']===0&&!str_starts_with($original['value'],'-')),'curated_dimension');
        $expected=array_replace($original,['period_start'=>$row['period_start'],'period_end'=>$row['period_end'],'fiscal_year'=>$row['fiscal_year'],
            'normalized_value'=>$row['value_decimal'],'normalized_unit'=>$row['unit_key'],'validation_status'=>'qualified_curated']);
        if($primary){
            check(is_string($original['locator'])&&strlen($original['locator'])>0&&strlen($original['locator'])<=255,'curated_locator');
            $expected+=array_intersect_key($row,array_flip(['period_type','fiscal_quarter','as_of_at']));
        }
        same(canonical($fact),canonical($expected),'curated_evidence_fact');
        same($row['field_path'],'curated-evidence:facts/'.$i.';manifest:facts/'.$i,'curated_locator');
    }
}
