<?php
declare(strict_types=1);
namespace Mosa2\Phase3D\NextBatch;
require_once __DIR__.'/dry_run.php';
use function Mosa2\Phase3D\{json,isinValid,secretFree};
use function Mosa2\Phase3C\{requireValue,normalizeObservationValues,normalizeObservation,dedupeKey};

// Pure offline evaluation of previously extracted evidence. No source reader,
// connection, clock, write adapter or provider request is part of this module.
function nameKey(string $name): string {
    $name=html_entity_decode(trim($name),ENT_QUOTES|ENT_HTML5,'UTF-8');
    $name=function_exists('mb_strtolower')?mb_strtolower($name,'UTF-8'):strtolower($name);
    return trim(preg_replace('/\s+/u',' ',preg_replace('/[^\p{L}\p{N}]+/u',' ',$name)??'')??'');
}
function frankfurtRecord(array $r): bool {
    $keys=array_keys($r);sort($keys);
    $expected=['user_id','asset_key','isin','provider_key','source_key','status','discovered_at','technical'];sort($expected);
    if($keys!==$expected||!is_int($r['user_id'])||$r['user_id']<1||!isinValid($r['isin'])
        ||!is_string($r['asset_key'])||!preg_match('/\A[a-z0-9][a-z0-9_-]{1,63}\z/D',$r['asset_key'])
        ||$r['provider_key']!=='boerse_frankfurt_api'||$r['status']!=='found'
        ||!is_string($r['source_key'])||!str_starts_with($r['source_key'],'boerse_frankfurt_api:'.$r['asset_key'].':')
        ||!is_array($r['technical']))return false;
    if(array_diff(array_keys($r['technical']),['mic','exchange_name','currency','timezone'])!==[]
        ||($r['technical']['mic']??null)!=='XFRA'||($r['technical']['currency']??null)!=='EUR')return false;
    foreach(['exchange_name','currency','timezone'] as $f)if(isset($r['technical'][$f])&&(!is_string($r['technical'][$f])||trim($r['technical'][$f])===''))return false;
    if(!is_string($r['discovered_at'])||!preg_match('/\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})\z/D',$r['discovered_at']))return false;
    try{new \DateTimeImmutable($r['discovered_at']);}catch(\Throwable){return false;}
    return true;
}
function assetEvidence(array $c): array {
    $r=['name_confirmed'=>false,'asset_class_confirmed'=>false,'canonical_name'=>null,'asset_class'=>null,
        'portfolio_row_sha256'=>null,'stock_records'=>0,'etf_records'=>0,'conflicts'=>[],'reasons'=>[]];
    if(!isinValid($c['isin']??null)){$r['reasons'][]='identifier_invalid';return $r;}
    $matches=array_values(array_filter($c['portfolio_rows']??[],static fn($x)=>$x['isin']===$c['isin']||$x['asset_key']===$c['source_asset_key']));
    if($matches===[]){$r['reasons'][]='portfolio_asset_not_found';return $r;}
    $names=[];$users=[];
    foreach($matches as $row){
        if($row['isin']!==$c['isin']||$row['asset_key']!==$c['source_asset_key']){$r['conflicts'][]='portfolio_identity_conflict';continue;}
        if(!is_int($row['user_id'])||$row['user_id']<1||($row['status']??null)!=='active'
            ||!is_string($row['mosa_object_key']??null)||!preg_match('/\Aobject_[a-f0-9]{24}\z/D',$row['mosa_object_key'])
            ||!is_string($row['display_name']??null)||trim($row['display_name'])===''||strlen($row['display_name'])>160){$r['reasons'][]='portfolio_name_invalid';continue;}
        // For these new, non-special candidates the existing bridge key is exact.
        if($row['asset_key']!=='isin_'.strtolower($c['isin'])){$r['conflicts'][]='portfolio_identity_conflict';continue;}
        $names[]=$row['display_name'];$users[$row['user_id']]=true;
    }
    foreach($c['consistency_names']??[] as $name){if(is_string($name)&&$name!=='')$names[]=$name;}
    if(count(array_unique(array_map(__NAMESPACE__.'\\nameKey',$names)))!==1)$r['conflicts'][]='name_conflict';
    if(count($matches)!==1||count($users)!==1)$r['reasons'][]='portfolio_context_ambiguous';
    if($r['reasons']!==[]||$r['conflicts']!==[])return $r;
    $row=$matches[0];$r['name_confirmed']=true;$r['canonical_name']=$row['display_name'];
    $r['portfolio_row_sha256']=hash('sha256',json($row));
    foreach($c['registrations']??[] as $registration){
        if(($registration['user_id']??null)===$row['user_id']&&($registration['asset_key']??null)===$c['source_asset_key']&&($registration['isin']??null)!==$c['isin'])$r['conflicts'][]='source_identity_conflict';
        if($registration['isin']!==$c['isin']||$registration['asset_key']!==$c['source_asset_key']||$registration['user_id']!==$row['user_id'])continue;
        if(frankfurtRecord($registration))$r['stock_records']++;
    }
    // ETF entries are evidence envelopes: the original reference validator and
    // active relationship/identity validation must already have succeeded.
    foreach($c['etf_evidence']??[] as $e){$ref=$e['record']??[];
        if(($e['reference_contract_valid']??false)!==true||($e['active_relationship_valid']??false)!==true)continue;
        if(($ref['contract_version']??null)==='mosa_etf_reference_v1'&&($ref['asset_type']??null)==='etf'
            &&($ref['isin']??null)===$c['isin']&&($ref['object_key']??null)===$c['isin']
            &&($ref['user_id']??null)===$row['user_id']&&isset($ref['object_name'])){
            if(nameKey($ref['object_name'])!==nameKey($row['display_name']))$r['conflicts'][]='name_conflict';
            $r['etf_records']++;
        }
    }
    if($r['stock_records']>0&&$r['etf_records']>0)$r['conflicts'][]='asset_class_conflict';
    if($r['stock_records']>1||$r['etf_records']>1)$r['reasons'][]='asset_class_ambiguous';
    $class=$r['stock_records']===1?'equity':($r['etf_records']===1?'etf':null);
    foreach($c['consistency_types']??[] as $type){if(!in_array($type,$class==='equity'?['EQUITY','STOCK']:['ETF'],true))$r['conflicts'][]='asset_class_conflict';}
    if($class===null)$r['reasons'][]='asset_class_missing';
    if($r['conflicts']===[]&&$r['reasons']===[]){$r['asset_class_confirmed']=true;$r['asset_class']=$class;}
    return $r;
}
function plan(array $input): array {
    // Private identities and numeric user context are required evidence, while
    // credentials have no role in this input. Check all other credential keys.
    $stripUser=static function(mixed $v)use(&$stripUser):mixed{if(!is_array($v))return $v;unset($v['user_id']);return array_map($stripUser,$v);};secretFree($stripUser($input));
    requireValue(count($input['candidates']??[])<=30,'candidate_limit');
    $target=$input['target_snapshot']??[];$facts=$target['facts']??[];$complete=($target['complete']??false)===true;
    $results=[];$seen=[];
    foreach($input['candidates'] as $c){
        requireValue(!isset($seen[$c['candidate_id']])&&!isset($seen[$c['source_reference']]),'candidate_identity');$seen[$c['candidate_id']]=true;$seen[$c['source_reference']]=true;
        $r=['candidate_id'=>$c['candidate_id'],'source_reference'=>$c['source_reference'],'eligible'=>false,'reasons'=>[],
            'asset'=>null,'source'=>null,'route'=>null,'observation'=>null,'dedupe_hex'=>null,'expected_action'=>'unresolved'];
        if(in_array($c['source_reference'],$input['already_imported_refs']??[],true)){$r['status']='already_imported';$results[]=$r;continue;}
        if(($c['original_transformable']??false)!==true||($c['target_type']??null)!=='observation'
            ||($c['native_market_quote']??false)!==true||($c['unit_class']??null)!=='currency_per_instrument'
            ||($c['time_semantics_confirmed']??false)!==true||in_array($c['observation']['currency']??null,['GBX','XXX'],true)){
            $r['status']='blocked';$r['reasons']=['original_scope_blocked'];$results[]=$r;continue;
        }
        $e=assetEvidence($c);$r['evidence']=$e;$r['reasons']=array_values(array_unique(array_merge($e['reasons'],$e['conflicts'])));
        if(!$complete)$r['reasons'][]='target_snapshot_missing';
        if(!$e['name_confirmed']||!$e['asset_class_confirmed']||$r['reasons']!==[]){$r['status']=$e['conflicts']!==[]?'BLOCKED_CONFLICT':(!$e['name_confirmed']?'BLOCKED_NAME':'BLOCKED_CLASS');$results[]=$r;continue;}
        $r['observation']=normalizeObservationValues($c['observation']);
        $ids=array_values(array_filter($facts['m2_asset_identifiers']??[],static fn($x)=>$x['identifier_type']==='isin'&&$x['scope_key']===''&&$x['normalized_value']===$c['isin']));
        requireValue(count($ids)<=1,'target_identifier_conflict');$assetId=$ids===[]?null:(string)$ids[0]['asset_id'];
        if($assetId!==null){$assets=array_values(array_filter($facts['m2_assets']??[],static fn($x)=>(string)$x['entity_id']===$assetId));
            requireValue(count($assets)===1&&$assets[0]['display_name']===$e['canonical_name']&&$assets[0]['asset_class']===$e['asset_class'],'target_asset_conflict');}
        $r['asset']=['state'=>$assetId===null?'new':'existing','asset_id'=>$assetId,'isin'=>$c['isin'],'source_asset_key'=>$c['source_asset_key'],'canonical_name'=>$e['canonical_name'],'display_name'=>$e['canonical_name'],'asset_class'=>$e['asset_class'],'base_currency'=>null];
        requireValue(preg_match('/\Aprovider:[a-z0-9_]+\z/D',$c['proposed_source_key'])===1,'source_contract');
        $sources=array_values(array_filter($facts['m2_sources']??[],static fn($x)=>$x['source_key']===$c['proposed_source_key']));requireValue(count($sources)<=1,'source_ambiguous');
        if($sources!==[])requireValue($sources[0]['source_type']==='market_data'&&(int)$sources[0]['enabled']===1,'source_conflict');
        $sourceId=$sources===[]?null:(string)$sources[0]['id'];$r['source']=['state'=>$sourceId===null?'new':'existing','source_key'=>$c['proposed_source_key'],'source_id'=>$sourceId];
        $external='market-v1:'.hash('sha256',$c['proposed_route_key']);$byExternal=[];$byAsset=[];
        foreach($facts['m2_asset_source_routes']??[] as $route){if($sourceId===null||(string)$route['source_id']!==$sourceId||$route['route_type']!=='quote')continue;
            if($route['external_key']===$external)$byExternal[]=$route;if($assetId!==null&&(string)$route['asset_id']===$assetId)$byAsset[]=$route;}
        requireValue(count($byExternal)<=1&&count($byAsset)<=1,'route_ambiguous');
        requireValue(($byExternal===[]&&$byAsset===[])||(count($byExternal)===1&&count($byAsset)===1&&(string)$byExternal[0]['id']===(string)$byAsset[0]['id']),'route_identity_conflict');
        $routeId=$byExternal===[]?null:(string)$byExternal[0]['id'];
        if($routeId!==null)requireValue((int)$byExternal[0]['enabled']===1&&(int)$byExternal[0]['priority']===0,'route_configuration_conflict');
        $r['route']=['state'=>$routeId===null?'new':'existing','route_id'=>$routeId,'proposed_route_key'=>$c['proposed_route_key'],'route_type'=>'quote','external_key'=>$external,'priority'=>0,'enabled'=>1];
        $r['expected_action']='planned_insert_after_catalog_resolution';
        if($assetId!==null&&$sourceId!==null&&$routeId!==null){
            $row=normalizeObservation(['asset_id'=>$assetId,'source_id'=>$sourceId,'route_id'=>$routeId]+$r['observation']);$r['dedupe_hex']=bin2hex(dedupeKey($row));$r['expected_action']='expected_insert';
            foreach($facts['m2_market_observations']??[] as $existing)if(strtolower($existing['dedupe_hex'])===$r['dedupe_hex']){
                foreach($row as $k=>$v)requireValue($v===null?$existing[$k]===null:(string)$existing[$k]===(string)$v,'dedupe_payload_conflict');$r['expected_action']='expected_duplicate';}
        }
        $r['status']='eligible';$r['eligible']=true;$results[]=$r;
    }
    usort($results,static fn($a,$b)=>strcmp($a['candidate_id'],$b['candidate_id']));
    $eligible=array_values(array_filter($results,static fn($r)=>$r['eligible']&&$r['expected_action']!=='expected_duplicate'));
    usort($eligible,static fn($a,$b)=>[$a['asset']['state']!=='existing',$a['source']['state']!=='existing',$a['route']['state']!=='existing',$a['source_reference']]<=>[$b['asset']['state']!=='existing',$b['source']['state']!=='existing',$b['route']['state']!=='existing',$b['source_reference']]);
    $selected=array_slice($eligible,0,3);foreach($selected as $i=>&$r)$r['sample_id']='P2-A'.($i+1);unset($r);
    $summary=['candidates'=>count($results),'eligible'=>count(array_filter($results,static fn($r)=>$r['eligible'])),'package_size'=>count($selected),'assets_existing'=>0,'assets_new'=>0,'sources_existing'=>0,'sources_new'=>0,'routes_existing'=>0,'routes_new'=>0,'planned_insert'=>0,'expected_insert'=>0,'expected_duplicate'=>0,'pending_dedupe_ids'=>0];$sets=[];
    foreach($selected as $r){foreach(['assets'=>['asset','isin'],'sources'=>['source','source_key'],'routes'=>['route','proposed_route_key']] as $plural=>[$field,$key])$sets[$plural.'_'.$r[$field]['state']][$r[$field][$key]]=true;
        $summary[$r['expected_action']==='planned_insert_after_catalog_resolution'?'planned_insert':$r['expected_action']]++;$summary['pending_dedupe_ids']+=(int)($r['dedupe_hex']===null);}
    foreach($sets as $key=>$set)$summary[$key]=count($set);
    $out=['contract_version'=>'mosa2-phase3dd-next-batch-v1','parents'=>$input['parents']??[],'results'=>$results,'selected'=>$selected,'summary'=>$summary,'write_authorized'=>false];
    $out['manifest_sha256']=hash('sha256',json($out));return $out;
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    try{requireValue($argc===2&&is_file($argv[1])&&!is_link($argv[1])&&filesize($argv[1])<=1048576,'input_file');echo json(plan(json_decode(file_get_contents($argv[1]),true,64,JSON_THROW_ON_ERROR)))."\n";}
    catch(\Throwable){fwrite(STDERR,"Offline planning evidence rejected; inspect privately.\n");exit(1);}
}
