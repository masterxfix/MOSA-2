<?php
declare(strict_types=1);
namespace Mosa2\Fundamentals;
use function Mosa2\Phase2\{check,same};

function hkexOriginalNumber(string $value): string {
    $value=trim(str_replace([',',' '],'',$value));$negative=str_starts_with($value,'(')&&str_ends_with($value,')');
    if($negative)$value=substr($value,1,-1);
    check(preg_match('/\A[0-9]+(?:\.[0-9]+)?\z/',$value)===1,'hkex_original_value');
    return decimal(($negative?'-':'').$value);
}

/** Independent binding for the bounded, official HKEX PDF adapter. */
function hkexEvidence(array $plan,array $doc):void {
    same($doc['format'],'mosa2-fundamental-evidence-v1','hkex_format');same($doc['kind'],'derived_evidence','hkex_kind');
    same($doc['evidence_type'],'hkex_pdf','hkex_type');same($plan['parser_key'],'hkex_consolidated_annual_pdf_v1','hkex_parser');
    same($plan['parser_version'],'1','hkex_version');same($plan['fiscal_year_start_month'],1,'hkex_calendar');
    same($doc['source_classification'],'official_hkex_annual_report','hkex_classification');
    same(canonical($doc['source_response']),canonical($plan['metadata']+['retained'=>false]),'hkex_response');
    same(canonical($doc['reported_periods']),canonical($plan['reported_periods']),'hkex_periods');
    $profile=$doc['identity_mapping'];$profiles=json_decode(file_get_contents(__DIR__.'/hkex_profiles.json'),true,32,JSON_THROW_ON_ERROR);
    check(count(array_filter($profiles,fn($p)=>canonical($p)===canonical($profile)))===1,'hkex_reviewed_profile');
    same(canonical($profile),canonical($plan['hkex_profile']),'hkex_plan_profile');
    same($doc['issuer'], $plan['identity'],'hkex_issuer');same($doc['issuer']['isin'],$profile['isin'],'hkex_isin');
    check(in_array($doc['issuer']['name'],$profile['names'],true),'hkex_name');same($plan['metadata']['url'],$profile['url'],'hkex_url');
    same($plan['metadata']['http_status'],200,'hkex_http');check(str_starts_with($plan['metadata']['content_type'],'application/pdf'),'hkex_mime');
    same($doc['reporting_standard'],$profile['standard'],'hkex_standard');same($doc['consolidation_status'],'consolidated','hkex_consolidation');
    same($plan['source']['source_key'],'hkex_official_annual_reports','hkex_source');same($plan['source']['enabled'],'0','hkex_disabled');
    foreach(['identity_evidence','standard_evidence','consolidation_evidence','period_evidence'] as $key){
        check(count($doc[$key])>=1&&count($doc[$key])<=4,'hkex_anchor_count');
        foreach($doc[$key] as $anchor){check(is_int($anchor['page'])&&$anchor['page']>=1,'hkex_anchor_page');check(is_string($anchor['excerpt'])&&strlen($anchor['excerpt'])>0&&strlen($anchor['excerpt'])<=1024,'hkex_anchor_excerpt');}
    }
    $identityText=implode(' ',array_column($doc['identity_evidence'],'excerpt'));check(stripos($identityText,$profile['name'])!==false,'hkex_identity_anchor');
    $standardText=implode(' ',array_column($doc['standard_evidence'],'excerpt'));check(preg_match('/ASBE|Accounting Standards for Business Enterprises/i',$standardText)===1,'hkex_standard_anchor');
    $scopeText=implode(' ',array_column($doc['consolidation_evidence'],'excerpt'));check(stripos($scopeText,'consolidated')!==false,'hkex_scope_anchor');
    $periodText=implode(' ',array_column($doc['period_evidence'],'excerpt'));check(stripos($periodText,'2025')!==false,'hkex_period_anchor');
    same(count($doc['facts']),count($plan['observations']),'hkex_fact_count');
    foreach($plan['observations'] as $i=>$row){
        $fact=$doc['facts'][$i];
        foreach(['metric_key','fiscal_year','period_start','period_end'] as $key)same($fact[$key],$row[$key],'hkex_fact');
        same($fact['normalized_value'],$row['value_decimal'],'hkex_value');same($fact['normalized_unit'],$row['unit_key'],'hkex_unit');
        same($fact['original_currency'],'CNY','hkex_currency');same($fact['original_unit'],$profile['original_unit'],'hkex_original_unit');
        same($fact['scale_numerator'],$profile['scale_numerator'],'hkex_scale');same($fact['scale_denominator'],$profile['scale_denominator'],'hkex_scale');
        same($fact['source_url'],$profile['url'],'hkex_source_url');same($fact['company'],$profile['name'],'hkex_company');
        same($fact['isin'],$profile['isin'],'hkex_fact_isin');same($fact['reporting_standard'],$profile['standard'],'hkex_fact_standard');
        same($fact['consolidation_status'],'consolidated','hkex_fact_scope');same($fact['validation_status'],'qualified','hkex_status');
        same($fact['normalized_value'],hkexOriginalNumber($fact['original_value']),'hkex_value_from_original');
        check(is_int($fact['page'])&&$fact['page']>=1,'hkex_fact_page');
        foreach(['table','row','column','position'] as $key)check(is_string($fact[$key])&&strlen($fact[$key])>0&&strlen($fact[$key])<=512,'hkex_locator');
        same($fact['column'],'FY'.$row['fiscal_year'],'hkex_column_year');
        $prefix='pdf:page='.$fact['page'].';table='.$fact['table'].';row='.$fact['row'].';column='.$fact['column'].';';
        check(str_starts_with($fact['position'],$prefix),'hkex_locator_binding');
        check(preg_match('/\Ax0=[0-9]{1,4}(?:\.[0-9]{1,3})?;y0=[0-9]{1,4}(?:\.[0-9]{1,3})?\z/',substr($fact['position'],strlen($prefix)))===1,'hkex_coordinates');
        same($row['field_path'],'evidence:facts/'.$i.';source='.$fact['position'],'hkex_field_path');
        same($row['reported_at'],null,'hkex_reported_at');same($row['as_of_at'],null,'hkex_asof');
    }
}
