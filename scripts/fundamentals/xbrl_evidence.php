<?php
declare(strict_types=1);
namespace Mosa2\Fundamentals;
use function Mosa2\Phase2\{check,same};

/** Qualified compact SEC evidence. Original-response hash is NOT the stored-file hash. */
function xbrlEvidence(array $plan,array $doc):void {
    same($doc['format'],'mosa2-fundamental-evidence-v1','xbrl_format');same($doc['kind'],'derived_evidence','xbrl_kind');
    same($plan['parser_key'],'sec_companyfacts_us_gaap_v1','xbrl_parser');same($plan['parser_version'],'1','xbrl_version');
    same($plan['fiscal_calendar'],'reported_fy','xbrl_calendar');same($plan['source']['source_key'],'sec_edgar_companyfacts','xbrl_source');
    same($plan['source']['source_type'],'regulator_xbrl','xbrl_source');same($plan['source']['enabled'],'0','xbrl_disabled');
    same($doc['source_classification'],'official_regulatory_filing','xbrl_classification');
    same(canonical($doc['source_response']),canonical($plan['metadata']+['retained'=>false]),'xbrl_response');
    same(canonical($doc['reported_periods']),canonical($plan['reported_periods']),'xbrl_periods');
    $mapping=$doc['identity_mapping'];$cik=$mapping['cik'];
    check(is_string($cik)&&preg_match('/\A[0-9]{10}\z/',$cik)===1,'xbrl_cik');
    same($mapping['verification'],'reviewed_cik_isin','xbrl_identity');same($mapping['isin'],$doc['issuer']['isin'],'xbrl_isin');
    $url='https://data.sec.gov/api/xbrl/companyfacts/CIK'.$cik.'.json';same($plan['metadata']['url'],$url,'xbrl_url');
    check(str_starts_with($mapping['reference'],'https://www.sec.gov/Archives/edgar/data/'.(string)(int)$cik.'/'),'xbrl_reference');
    same($plan['metadata']['http_status'],200,'xbrl_http');
    check(str_starts_with($plan['metadata']['content_type'],'application/json'),'xbrl_mime');
    $tags=['Revenues'=>'revenue','RevenueFromContractWithCustomerIncludingAssessedTax'=>'revenue','RevenueFromContractWithCustomerExcludingAssessedTax'=>'revenue','OperatingIncomeLoss'=>'operating_income',
        'NetIncomeLoss'=>'profit_attributable_to_owners','ProfitLoss'=>'profit_after_tax','NetCashProvidedByUsedInOperatingActivities'=>'operating_cashflow'];
    $validateReference=static function(array $ref,string $start,string $end,string $year)use($plan):void{
        same($ref['start'],$start,'xbrl_start');same($ref['end'],$end,'xbrl_end');same($ref['fp'],'FY','xbrl_fp');
        check(in_array($ref['form'],['10-K','10-K/A'],true),'xbrl_form');
        check(preg_match('/\A[0-9]{10}-[0-9]{2}-[0-9]{6}\z/',$ref['accession'])===1,'xbrl_accession');
        $date=\DateTimeImmutable::createFromFormat('!Y-m-d',$ref['filed']);check($date!==false&&$date->format('Y-m-d')===$ref['filed'],'xbrl_filed');
        check($ref['filed']>=$end&&$ref['filed']<=substr($plan['metadata']['observed_at'],0,10),'xbrl_publication');
        check(preg_match('/\A[1-9][0-9]{3}\z/',$ref['filing_fy'])===1,'xbrl_filing_fy');
        same($ref['role'],$ref['form']==='10-K/A'?'amendment':($ref['filing_fy']===$year?'current':'comparative'),'xbrl_role');
        check(preg_match('/\Ajson:\/facts\/us-gaap\/[A-Za-z0-9]+\/units\/USD\/[0-9]+\z/',$ref['position'])===1,'xbrl_position');
        decimal($ref['value']);
    };
    check(count($plan['reported_periods'])===2,'xbrl_period_count');$previous=null;
    foreach($plan['reported_periods'] as $year=>$period){
        $ref=$period['anchor'];$validateReference($ref,$period['start'],$period['end'],(string)$year);
        same($ref['form'],'10-K','xbrl_anchor_form');same($ref['filing_fy'],(string)$year,'xbrl_anchor_year');same($ref['role'],'current','xbrl_anchor_role');
        if($previous!==null){same((int)$year,$previous['year']+1,'xbrl_consecutive_years');same($period['start'],(new \DateTimeImmutable($previous['end']))->modify('+1 day')->format('Y-m-d'),'xbrl_consecutive_dates');}
        $previous=['year'=>(int)$year,'end'=>$period['end']];
    }
    same(count($doc['facts']),count($plan['observations']),'xbrl_count');
    foreach($plan['observations'] as $i=>$row){
        $fact=$doc['facts'][$i];same($fact['taxonomy'],'us-gaap','xbrl_taxonomy');same($tags[$fact['tag']]??null,$row['metric_key'],'xbrl_tag');
        if($row['metric_key']==='revenue'&&$fact['tag']!=='RevenueFromContractWithCustomerExcludingAssessedTax'){
            $review=$fact['revenue_review'];same($review['scope'],'consolidated_total_revenue','revenue_scope');same($review['tag'],$fact['tag'],'revenue_tag');
            same($review['reference'],$mapping['reference'],'revenue_reference');same($review['fiscal_year'],$row['fiscal_year'],'revenue_year');
            same($review['start'],$row['period_start'],'revenue_start');same($review['end'],$row['period_end'],'revenue_end');
            same(decimal($review['control_usd']),decimal($row['value_decimal']),'revenue_control');
            check(is_string($fact['concept_definition'])&&strlen($fact['concept_definition'])>0&&strlen($fact['concept_definition'])<=4096,'revenue_definition');
            check(in_array($review,$mapping['revenue_reviews'],true),'revenue_review_binding');
        }
        foreach(['metric_key','period_start','period_end','fiscal_year'] as $k)same($fact[$k],$row[$k],'xbrl_fact');
        same($fact['normalized_value'],$row['value_decimal'],'xbrl_value');same($fact['original_value'],$row['value_decimal'],'xbrl_original');
        same($fact['original_unit'],'USD','xbrl_unit');same($fact['normalized_unit'],'USD','xbrl_unit');same($row['unit_key'],'USD','xbrl_unit');
        same($fact['cik'],$cik,'xbrl_cik');same($fact['source_url'],$url,'xbrl_url');same($fact['validation_status'],'qualified','xbrl_status');
        same($row['field_path'],'evidence:facts/'.$i.';source='.$fact['position'],'xbrl_locator');
        check(str_starts_with($fact['position'],'json:/facts/us-gaap/'.$fact['tag'].'/units/USD/'),'xbrl_tag_locator');
        same($fact['position'],$fact['selected']['position'],'xbrl_selected');
        check(count($fact['occurrences'])>=1&&count($fact['occurrences'])<=64,'xbrl_occurrences');$selected=false;
        foreach($fact['occurrences'] as $ref){$validateReference($ref,$row['period_start'],$row['period_end'],$row['fiscal_year']);
            same(decimal($ref['value']),decimal($row['value_decimal']),'xbrl_conflict');
            check(str_starts_with($ref['position'],'json:/facts/us-gaap/'.$fact['tag'].'/units/USD/'),'xbrl_occurrence_tag');
            if(canonical($ref)===canonical($fact['selected']))$selected=true;
        }
        check($selected,'xbrl_selected_occurrence');same($row['reported_at'],null,'xbrl_date_only');same($row['as_of_at'],null,'xbrl_no_asof');
    }
}
