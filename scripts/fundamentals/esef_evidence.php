<?php
declare(strict_types=1);
namespace Mosa2\Fundamentals;
use function Mosa2\Phase2\{check,same};

/** Independent evidence/plan binding; Arelle performs the Inline transformations. */
function esefEvidence(array $plan,array $doc):void {
    same($doc['format'],'mosa2-fundamental-evidence-v1','esef_format');same($doc['kind'],'derived_evidence','esef_kind');
    same($plan['parser_key'],'esef_ifrs_inline_v1','esef_parser');same($plan['parser_version'],'1','esef_version');
    same($doc['arelle_version'],'2.47.3','esef_library');same($doc['qualification_scope'],'allowlisted_IFRS_facts_not_full_DTS_validation','esef_scope');
    same($doc['source_classification'],'official_issuer_esef','esef_classification');
    same($plan['fiscal_calendar'],'reported_fy','esef_calendar');
    same(canonical($doc['source_response']),canonical($plan['metadata']+['retained'=>false]),'esef_response');
    same(canonical($doc['reported_periods']),canonical($plan['reported_periods']),'esef_periods');
    $profile=$doc['identity_mapping'];$profiles=json_decode(file_get_contents(__DIR__.'/esef_profiles.json'),true,32,JSON_THROW_ON_ERROR);
    check(count(array_filter($profiles,fn($p)=>canonical($p)===canonical($profile)))===1,'esef_reviewed_profile');
    same($doc['issuer']['isin'],$profile['isin'],'esef_isin');check(in_array($doc['issuer']['name'],$profile['names'],true),'esef_name');
    same(canonical($plan['source']),canonical($profile['source']),'esef_source');
    same($plan['metadata']['url'],$profile['url'],'esef_url');same($plan['metadata']['http_status'],200,'esef_http');
    same($plan['metadata']['execution'],$profile['execution'],'esef_execution');
    $ifrs=static fn(string $ns):bool=>preg_match('~\Ahttps?://xbrl.ifrs.org/taxonomy/20[0-9]{2}-[0-9]{2}-[0-9]{2}/ifrs-full\z~',$ns)===1;
    $record=static function(array $r,bool $contextEnd=false)use($profile,$ifrs):void{
        if($contextEnd){same($r['taxonomy'],'http://www.xbrl.org/2003/instance','esef_context_taxonomy');same($r['tag'],'xbrli:endDate','esef_context_tag');}
        else check($ifrs($r['taxonomy']),'esef_taxonomy');
        same($r['entity'],$profile['lei'],'esef_lei');
        check(in_array($r['entity_scheme'],['http://standards.iso.org/iso/17442','https://standards.iso.org/iso/17442'],true),'esef_scheme');
        check(is_string($r['context_id'])&&strlen($r['context_id'])>0&&strlen($r['context_id'])<=256,'esef_context');
        foreach($r['dimensions'] as $axis=>$member){
            check(preg_match('~\A\{(https?://xbrl.ifrs.org/taxonomy/20[0-9]{2}-[0-9]{2}-[0-9]{2}/ifrs-full)\}ConsolidatedAndSeparateFinancialStatementsAxis\z~',$axis)===1,'esef_axis');
            check(preg_match('~\A\{(https?://xbrl.ifrs.org/taxonomy/20[0-9]{2}-[0-9]{2}-[0-9]{2}/ifrs-full)\}ConsolidatedMember\z~',$member)===1,'esef_member');
        }
        check(preg_match('/\A[0-9a-f]{64}\z/',$r['member_sha256'])===1,'esef_member_hash');
        check(is_string($r['member'])&&strlen($r['member'])<=220&&!str_contains($r['member'],'..')&&!str_contains($r['member'],'\\')&&!str_contains($r['member'],':')&&!str_starts_with($r['member'],'/'),'esef_member_path');
        if($contextEnd)check(str_starts_with($r['position'],'context:'.$r['member'].'#id=')&&str_ends_with($r['position'],'/endDate'),'esef_context_position');
        else check(str_starts_with($r['position'],'ix:'.$r['member'].'#element=')&&preg_match('/#element=[0-9]+\z/',$r['position'])===1,'esef_position');
    };
    $scopeMatches=static function(array $r):bool{
        $value=$r['value'];$tag=$r['tag'];
        if($tag==='DescriptionOfNatureOfFinancialStatements')return preg_match('/\bconsolidated\b/i',$value)===1&&preg_match('/\b(non.consolidated|unconsolidated|not\s+consolidated)\b/i',$value)!==1;
        if($tag==='DisclosureOfBasisOfPreparationOfFinancialStatementsExplanatory')return preg_match('/\bconsolidated\b/i',$value)===1&&preg_match('/\bfinancial\b/i',$value)===1&&preg_match('/\bstatements\b/i',$value)===1;
        if($tag==='DisclosureOfBasisOfConsolidationExplanatory')return preg_match('/\bconsolidated\b/i',$value)===1&&preg_match('/\bparent\b/i',$value)===1&&preg_match('/\bsubsidiaries\b/i',$value)===1;
        return false;
    };
    foreach(['identity_evidence','consolidation_evidence','report_end_evidence'] as $key){
        check(count($doc[$key])>=1&&count($doc[$key])<=32,'esef_anchor');
        foreach($doc[$key] as $r){$contextEnd=$key==='report_end_evidence'&&$r['tag']==='xbrli:endDate';$record($r,$contextEnd);same($r['numeric'],false,'esef_anchor_kind');
            if($key==='identity_evidence'){
                same($r['tag'],'NameOfReportingEntityOrOtherMeansOfIdentification','esef_identity_tag');
                $norm=static fn($v)=>preg_replace('/[^A-Z0-9]/','',strtoupper($v));check(in_array($norm($r['value']),array_map($norm,$profile['names']),true),'esef_entity_name');
            }elseif($key==='consolidation_evidence'){
                check($scopeMatches($r),'esef_consolidated');
            }else{if($contextEnd){same($r['value'],$profile['report_end'],'esef_end');}else{same($r['tag'],'DateOfEndOfReportingPeriod2013','esef_end_tag');same($r['value'],$profile['report_end'],'esef_end');}}
        }
    }
    same(array_map('intval',array_keys($plan['reported_periods'])),$profile['years'],'esef_years');$prev=null;
    foreach($plan['reported_periods'] as $year=>$period){
        same(substr($period['end'],0,4),(string)$year,'esef_year_label');
        if($prev!==null)same($period['start'],(new \DateTimeImmutable($prev))->modify('+1 day')->format('Y-m-d'),'esef_continuity');$prev=$period['end'];
    }same($prev,$profile['report_end'],'esef_latest_end');
    $tags=['Revenue'=>'revenue','ProfitLossFromOperatingActivities'=>'ifrs_operating_profit','ProfitLossBeforeTax'=>'profit_before_tax','ProfitLoss'=>'profit_after_tax','CashFlowsFromUsedInOperatingActivities'=>'operating_cashflow'];
    same(count($doc['facts']),count($plan['observations']),'esef_count');
    foreach($plan['observations'] as $i=>$row){
        $f=$doc['facts'][$i];$r=$f['selected'];$record($r);
        foreach(['identity_evidence','consolidation_evidence','report_end_evidence'] as $anchor){
            check(count(array_filter($doc[$anchor],fn($a)=>$a['member']===$r['member']&&$a['member_sha256']===$r['member_sha256']))>=1,'esef_report_scope');
        }
        same($tags[$r['tag']]??null,$row['metric_key'],'esef_tag');same($r['numeric'],true,'esef_numeric');
        foreach(['metric_key','fiscal_year','period_start','period_end'] as $k)same($f[$k],$row[$k],'esef_fact');
        same($f['normalized_value'],$row['value_decimal'],'esef_value');same($f['normalized_unit'],$row['unit_key'],'esef_unit');
        same($f['original_unit'],$row['unit_key'],'esef_unit');same($row['unit_key'],$profile['expected_currency'],'esef_currency');
        same($f['source_url'],$profile['url'],'esef_source_url');same($f['validation_status'],'qualified','esef_status');
        same($row['field_path'],'evidence:facts/'.$i.';source='.$r['position'],'esef_locator');
        check(count($f['occurrences'])>=1&&count($f['occurrences'])<=32,'esef_occurrences');$selected=false;
        foreach($f['occurrences'] as $o){$record($o);same($o['tag'],$r['tag'],'esef_tag');same($o['numeric'],true,'esef_numeric');
            same(decimal($o['value']),decimal($row['value_decimal']),'esef_conflict');same($o['currency'],$row['unit_key'],'esef_currency');
            same($o['start'],$row['period_start'],'esef_start');same($o['end'],$row['period_end'],'esef_end');
            check(is_string($o['original_value'])&&strlen($o['original_value'])<=2048,'esef_original');
            check(preg_match('/\A-?[0-9]{1,2}\z/',$o['scale'])===1&&abs((int)$o['scale'])<=18,'esef_scale');
            check(in_array($o['sign'],['','-'],true),'esef_sign');
            check(is_string($o['decimals'])&&preg_match('/\A(?:INF|-?[0-9]{1,2})\z/',$o['decimals'])===1,'esef_decimals');
            if(canonical($o)===canonical($r))$selected=true;
        }check($selected,'esef_selected');same($row['reported_at'],null,'esef_no_timestamp');same($row['as_of_at'],null,'esef_no_asof');
    }
}
