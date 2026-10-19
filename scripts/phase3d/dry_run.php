<?php
declare(strict_types=1);
namespace Mosa2\Phase3D;

require_once dirname(__DIR__).'/phase3c/market_flow.php';
use InvalidArgumentException;
use function Mosa2\Phase3C\{requireValue,identity,decimal,compareDecimal,utcTimestamp,normalizeObservationValues,normalizeObservation,dedupeKey};

// Pure offline proposal evaluator. Input is an already extracted private snapshot.
// No database, provider, collector, credentials, clock or persistence adapter.
function canonical(mixed $value): mixed {
    if(!is_array($value))return $value;
    if(!array_is_list($value))ksort($value,SORT_STRING);
    return array_map(__NAMESPACE__.'\\canonical',$value);
}
function json(mixed $value): string {
    return json_encode(canonical($value),JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
}
function secretFree(mixed $value): void {
    if(is_array($value))foreach($value as $key=>$item){
        requireValue(!is_string($key)||!preg_match('/password|secret|cookie|token|authorization|credential|user_id/i',$key),'secret_field');
        secretFree($item);
    }
    if(is_string($value))requireValue(!preg_match('/Bearer\s+|-----BEGIN .*PRIVATE KEY|mysql:host=|https?:\/\/[^\s\/]+:[^\s\/]+@/i',$value),'secret_value');
}
function isinValid(mixed $value): bool {
    if(!is_string($value)||!preg_match('/\A[A-Z]{2}[A-Z0-9]{9}[0-9]\z/D',$value))return false;
    $digits='';foreach(str_split($value) as $c)$digits.=ctype_digit($c)?$c:(string)(ord($c)-55);
    $sum=0;$double=false;
    foreach(array_reverse(str_split($digits)) as $d){$n=(int)$d*($double?2:1);$sum+=intdiv($n,10)+$n%10;$double=!$double;}
    return $sum%10===0;
}
function timeValue(mixed $value,string $semantics): string {
    if($semantics==='utc')return utcTimestamp($value);
    if($semantics==='epoch_s'){
        requireValue(is_int($value)||(is_string($value)&&ctype_digit($value)),'market_time_unknown');
        return utcTimestamp((new \DateTimeImmutable('@'.$value))->setTimezone(new \DateTimeZone('UTC'))->format('Y-m-d H:i:s.u'));
    }
    if($semantics==='explicit_offset'){
        requireValue(is_string($value)&&(bool)preg_match('/\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})\z/D',$value),'timezone_ambiguous');
        $date=new \DateTimeImmutable($value);
        requireValue(\DateTimeImmutable::getLastErrors()===false,'utc_timestamp');
        return utcTimestamp($date->setTimezone(new \DateTimeZone('UTC'))->format('Y-m-d H:i:s.u'));
    }
    throw new InvalidArgumentException($semantics==='ambiguous'?'timezone_ambiguous':'market_time_unknown');
}
function candidate(array $entry,array $catalog=[]): array {
    $s=$entry['row'];$p=$entry['proof']??[];$reasons=[];$reject=false;
    $out=['sample_id'=>$entry['sample_id'],'source_reference'=>$entry['source_reference'],
        'family'=>$entry['family'],'asset_identity'=>'unresolved','resolved_asset_id'=>null,
        'proposed_asset_key'=>null,'proposed_source_key'=>null,'proposed_route_key'=>null,
        'target_type'=>($entry['target_type']??'observation'),'normalized_values'=>null,
        'dedupe_key'=>null,'bar_identity'=>null,'transformation_valid'=>false,
        'current_relevant'=>'unresolved','current_reason'=>'current_route_unselected',
        'unit_class'=>$p['unit_class']??'unknown','evidence'=>$p];
    $isin=$s['isin']??null;$contextIsin=$p['context_isin']??null;
    if(($p['identity_conflict']??false)||($isin!==null&&$contextIsin!==null&&$isin!==$contextIsin)){
        $out['asset_identity']='identity_conflict';$reasons[]='identity_conflict';$reject=true;
    }elseif($isin!==null&&!isinValid($isin)){$reasons[]='identifier_invalid';$reject=true;
    }elseif(isinValid($isin)){$out['asset_identity']='unique';$out['proposed_asset_key']='isin:'.$isin;
    }elseif(isset($p['unique_identifier']['type'],$p['unique_identifier']['value'],$p['unique_identifier']['scope'],$p['unique_identifier']['reference'])&&($p['unique_identifier']['matches']??0)===1){
        $out['asset_identity']='unique';$out['proposed_asset_key']='identifier:'.json($p['unique_identifier']);
    }else{$reasons[]='asset_identity_missing';}

    $provider=$s['provider_key']??null;$venue=$s['venue_key']??null;
    if(is_string($provider)&&$provider!=='')$out['proposed_source_key']='provider:'.$provider;
    $external=$p['external_identity']??null;
    if(($p['route_identity_conflict']??false)){$reasons[]='route_identity_conflict';$reject=true;
    }elseif(!$out['proposed_asset_key']||!$out['proposed_source_key']||!is_string($venue)||$venue===''||!is_array($external)||$external===[]||empty($p['route_reference'])){$reasons[]='route_unresolved';
    }else{
        $out['proposed_route_key']='route:'.json(['asset'=>$out['proposed_asset_key'],'provider'=>$provider,
            'venue'=>$venue,'currency'=>$s['currency']??null,'quote_variant'=>$p['quote_variant']??($s['quote_variant']??null),
            'series'=>$s['series']??null,'kind'=>$s['observation_kind']??null,'external'=>$external]);
    }
    $currency=$s['currency']??null;$unit=$out['unit_class'];
    if(!is_string($currency)||!preg_match('/\A[A-Z]{3}\z/D',$currency)||$currency==='XXX')$reasons[]='unit_or_currency_missing';
    if($currency==='GBX'&&($p['gbx_scale']??null)!=='0.01')$reasons[]='unit_scale_required';
    // Retain native GBX values; a scale proof does not silently convert them to GBP.
    if(!in_array($unit,['currency_per_instrument','currency_pair'],true))$reasons[]='unit_contract_unresolved';
    if(($s['observation_kind']??null)==='derived_quote'){
        $lineage=$p['derived_inputs']??[];
        foreach(['native_source','fx_source','native_price','native_currency','fx_symbol','fx_rate','native_market_at','fx_market_at','native_observed_at','fx_observed_at','native_fingerprint','fx_fingerprint','reproduction_reference'] as $field)
            if(!isset($lineage[$field])||$lineage[$field]===''){$reasons[]='derived_provenance_unresolved';break;}
        // This slice has no exact decimal FX arithmetic/reproduction adapter.
        // A populated lineage alone never proves the multiplication.
        $reasons[]='derived_provenance_unresolved';
    }
    $times=[];
    foreach(['market_at'=>'quoted_at','observed_at'=>'collected_at'] as $target=>$source){
        try{
            if(empty($p['producer_reference']))throw new InvalidArgumentException('timezone_ambiguous');
            $times[$target]=timeValue($s[$source]??null,$p[$target.'_semantics']??'unknown');
        }catch(\Throwable $e){$reasons[]=in_array($e->getMessage(),['timezone_ambiguous','market_time_unknown'],true)?$e->getMessage():'timestamp_invalid';}
    }
    $out['known_market_at']=$times['market_at']??null;
    if($out['target_type']==='bar'){
        if(!in_array($p['interval_key']??null,['1m','5m','1h','1d'],true)||empty($p['interval_reference']))$reasons[]='interval_unknown';
        if(empty($p['ends_at'])||empty($p['end_reference']))$reasons[]='bar_end_unknown';
        if(empty($p['adjustment_reference'])||empty($p['revision_reference']))$reasons[]='adjustment_unknown';
        $values=['currency'=>$currency,'starts_at'=>$times['market_at']??null,'ends_at'=>$p['ends_at']??null,
            'interval_key'=>$p['interval_key']??null,'observed_at'=>$times['observed_at']??null];
        try{
            foreach(['open','high','low','close'] as $v)$values[$v]=decimal($s['bar_'.$v]??null,28,10);
            $values['volume']=decimal($s['bar_volume']??null,32,8,true);
            requireValue(compareDecimal($values['low'],$values['high'])<=0,'ohlc');
            foreach(['open','close'] as $v)requireValue(compareDecimal($values[$v],$values['low'])>=0&&compareDecimal($values[$v],$values['high'])<=0,'ohlc');
            requireValue(compareDecimal($values['low'],'0.0000000000')>0,'ohlc');
            if($values['ends_at']!==null){$values['ends_at']=utcTimestamp($values['ends_at']);requireValue($values['starts_at']!==null&&$values['ends_at']>$values['starts_at'],'bar_end');}
        }catch(\Throwable){$reasons[]='bar_values_invalid';$reject=true;}
        $out['normalized_values']=$values;$out['current_relevant']='no';$out['current_reason']='bar_not_current';
    }elseif($out['target_type']==='observation'){
        try{
            if(count($times)===2&&is_string($currency)&&preg_match('/\A[A-Z]{3}\z/D',$currency))
                $out['normalized_values']=normalizeObservationValues(['currency'=>$currency]+$times+[
                    'price'=>$s['last_price']??null,'bid'=>$s['bid_price']??null,'ask'=>$s['ask_price']??null,
                    // Cumulative daily volume and turnover are not point trade volume.
                    'volume'=>$p['point_volume']??null]);
        }catch(\Throwable){$reasons[]='observation_values_invalid';$reject=true;}
    }else{$reasons[]='target_type_invalid';$reject=true;}
    $reasons=array_values(array_unique($reasons));sort($reasons,SORT_STRING);
    $out['transformation_valid']=!$reject&&$reasons===[]&&$out['normalized_values']!==null;
    if($out['transformation_valid']){
        $resolved=$catalog[$out['proposed_route_key']]??null;
        if(is_array($resolved)&&($resolved['proposed_asset_key']??null)===$out['proposed_asset_key']&&($resolved['proposed_source_key']??null)===$out['proposed_source_key']){
            $out['resolved_asset_id']=identity($resolved['asset_id']);
            if($out['target_type']==='observation'){
                $row=normalizeObservation(['asset_id'=>$resolved['asset_id'],'source_id'=>$resolved['source_id'],'route_id'=>$resolved['route_id']]+$out['normalized_values']);
                $out['dedupe_key']=bin2hex(dedupeKey($row));
            }else{$out['bar_identity']=['asset_id'=>identity($resolved['asset_id']),'route_id'=>identity($resolved['route_id']),'interval_key'=>$p['interval_key'],'starts_at'=>$times['market_at']];}
        }
        if($out['target_type']==='observation'&&isset($p['selected_route_key'])&&$p['selected_route_key']===$out['proposed_route_key']&&!empty($p['selection_reference'])){
            $out['current_relevant']='yes';$out['current_reason']='explicit_selected_route';
        }
        $reasons[]='target_snapshot_missing';
    }
    if($out['target_type']==='observation'&&$out['current_relevant']==='unresolved')$reasons[]='current_route_unselected';
    $reasons=array_values(array_unique($reasons));sort($reasons,SORT_STRING);
    $out['action']=$reject?'reject':'unresolved';
    $primary=array_values(array_diff($reasons,['current_route_unselected']));
    $out['reason']=$reject&&in_array('identity_conflict',$reasons,true)?'identity_conflict':($primary[0]??'current_route_unselected');
    $out['reasons']=$reasons;return $out;
}
function report(array $input): array {
    secretFree($input);
    requireValue(isset($input['manifest'],$input['candidates'])&&is_array($input['manifest'])&&is_array($input['candidates']),'snapshot_format');
    requireValue(count($input['candidates'])<=30,'sample_limit');
    $rows=[];$refs=[];$samples=[];
    foreach($input['candidates'] as $entry){
        requireValue(is_string($entry['source_reference']??null)&&is_string($entry['sample_id']??null)&&!isset($samples[$entry['sample_id']]),'sample_identity');
        $samples[$entry['sample_id']]=true;$refs[$entry['source_reference']]=true;
        $rows[]=candidate($entry,$input['target_catalog']??[]);
    }
    usort($rows,static fn($a,$b)=>strcmp($a['sample_id'],$b['sample_id']));
    $sum=['source_objects'=>count($refs),'target_candidates'=>count($rows),'transformable'=>0,'insert'=>0,'duplicate'=>0,'reject'=>0,'unresolved'=>0,
        'reasons'=>[],'observations'=>0,'bars'=>0,'current_relevant'=>['yes'=>0,'no'=>0,'unresolved'=>0],
        'proposed_assets'=>0,'proposed_sources'=>0,'proposed_routes'=>0,'currencies'=>[],'unit_classes'=>[],'market_at_min'=>null,'market_at_max'=>null];
    $sets=['proposed_asset_key'=>[],'proposed_source_key'=>[],'proposed_route_key'=>[]];$times=[];
    foreach($rows as $r){
        $sum[$r['action']]++;$sum['transformable']+=(int)$r['transformation_valid'];$sum[$r['target_type']==='bar'?'bars':'observations']++;
        $sum['current_relevant'][$r['current_relevant']]++;
        foreach($r['reasons'] as $reason)$sum['reasons'][$reason]=($sum['reasons'][$reason]??0)+1;
        $ccy=$r['normalized_values']['currency']??'unknown';$sum['currencies'][$ccy]=($sum['currencies'][$ccy]??0)+1;
        $sum['unit_classes'][$r['unit_class']]=($sum['unit_classes'][$r['unit_class']]??0)+1;
        foreach($sets as $field=>$_)if($r[$field]!==null)$sets[$field][$r[$field]]=true;
        if($r['known_market_at']!==null)$times[]=$r['known_market_at'];
    }
    foreach(['proposed_assets'=>'proposed_asset_key','proposed_sources'=>'proposed_source_key','proposed_routes'=>'proposed_route_key'] as $s=>$f)$sum[$s]=count($sets[$f]);
    if($times!==[]){sort($times,SORT_STRING);$sum['market_at_min']=$times[0];$sum['market_at_max']=$times[count($times)-1];}
    requireValue($sum['target_candidates']===$sum['insert']+$sum['duplicate']+$sum['reject']+$sum['unresolved'],'conservation');
    $report=['contract'=>'mosa2-phase3d-dry-run-v1','manifest'=>$input['manifest'],'results'=>$rows,'summary'=>$sum];
    $report['report_sha256']=hash('sha256',json($report));return canonical($report);
}
// Deliberate allowlist: no candidate, identity, exact source reference or manifest.
function publicSummary(array $report): array {return ['contract'=>$report['contract'],'summary'=>$report['summary']];}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    try{
        requireValue($argc===2,'usage_snapshot_path');
        requireValue(is_file($argv[1])&&!is_link($argv[1])&&filesize($argv[1])<=1048576,'snapshot_file');
        $input=json_decode(file_get_contents($argv[1]),true,64,JSON_THROW_ON_ERROR);
        echo json(report($input))."\n";
    }catch(\Throwable){fwrite(STDERR,"Offline snapshot rejected; inspect locally without publishing input.\n");exit(1);}
}
