<?php
declare(strict_types=1);
namespace Mosa2\Fundamentals;
use function Mosa2\Phase2\{check,same};

/** Independent binding for the one approved NEL Q2 PDF adapter. */
function nelQ2Evidence(array $plan,array $doc): void {
    same($doc['format'],'mosa2-fundamental-evidence-v1','nel_format');
    same($doc['kind'],'derived_evidence','nel_kind');
    same($doc['evidence_type'],'nel_q2_pdf','nel_type');
    same($plan['parser_key'],'nel_q2_2026_pdf_v1','nel_parser');
    same($plan['parser_version'],'1','nel_version');
    same($doc['source_classification'],'official_issuer_quarterly_report','nel_classification');
    same(canonical($doc['source_response']),canonical($plan['metadata']+['retained'=>false]),'nel_response');
    same($doc['issuer'],$plan['identity'],'nel_issuer');
    same($doc['issuer']['isin'],'NO0010081235','nel_isin');
    same($doc['issuer']['name'],'NEL ASA','nel_name');
    same($plan['source']['source_key'],'nel_official_quarterly_reports','nel_source');
    same($plan['source']['enabled'],'0','nel_source_disabled');
    same($plan['metadata']['url'],'https://mb.cision.com/Public/115/4374557/96afc9701633c3dd.pdf','nel_url');
    same($plan['metadata']['http_status'],200,'nel_http');
    check(str_starts_with($plan['metadata']['content_type'],'application/pdf'),'nel_mime');
    same($doc['publication_date'],'2026-07-15','nel_publication');
    same(canonical($doc['reported_periods']),canonical(['2026-Q2'=>['start'=>'2026-04-01','end'=>'2026-06-30']]),'nel_periods');
    same(count($plan['observations']),5,'nel_count');
    same(array_column($plan['observations'],'metric_key'),['revenue','ebitda','ifrs_operating_profit','profit_after_tax','operating_cashflow'],'nel_metric_order');
    same(count($doc['facts']),5,'nel_fact_count');
    foreach($plan['observations'] as $index=>$row){
        $fact=$doc['facts'][$index];
        foreach(['metric_key','fiscal_year','fiscal_quarter','period_start','period_end'] as $key)same($fact[$key],$row[$key],'nel_fact');
        same($fact['normalized_value'],$row['value_decimal'],'nel_value');
        same($fact['normalized_unit'],'NOK_THOUSAND','nel_unit');same($fact['original_unit'],'NOK_THOUSAND','nel_original_unit');
        same($fact['original_currency'],'NOK','nel_currency');same($fact['scale_numerator'],'1000','nel_scale');same($fact['scale_denominator'],'1','nel_scale');
        same($fact['source_url'],$plan['metadata']['url'],'nel_source_url');same($fact['company'],'NEL ASA','nel_company');same($fact['isin'],'NO0010081235','nel_fact_isin');
        same($fact['validation_status'],'qualified','nel_status');
        check(is_int($fact['page'])&&$fact['page']>=1,'nel_page');
        foreach(['table','row','column','position'] as $key)check(is_string($fact[$key])&&strlen($fact[$key])>0&&strlen($fact[$key])<=512,'nel_locator');
        same($fact['column'],'Q2 2026','nel_column');
        check(preg_match('/\Apdf:page=[1-9][0-9]*;table=.+;row=.+;column=Q2 2026;x0=[0-9]{1,4}(?:\.[0-9]{1,3})?;y0=[0-9]{1,4}(?:\.[0-9]{1,3})?\z/',$fact['position'])===1,'nel_locator');
        same($row['field_path'],'evidence:facts/'.$index.';source='.$fact['position'],'nel_field_path');
        same($row['reported_at'],null,'nel_reported_at');same($row['as_of_at'],null,'nel_asof');
    }
    same(count($doc['special_effects']),1,'nel_special_effect_count');
    same($doc['special_effects'][0]['treatment'],'evidence_only_no_ebitda_adjustment','nel_special_effect_treatment');
    check(stripos($doc['special_effects'][0]['excerpt'],'Iwatani')!==false,'nel_special_effect_source');
}
