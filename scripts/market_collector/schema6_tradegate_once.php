<?php
declare(strict_types=1);
namespace Mosa2\Schema6TradegateOnce;

use Throwable;
use function Mosa2\Phase2\{check,same,connection};

const AUTHORIZATION_PREFIX='MOSA2-PNE-TRADEGATE-ONE-SHOT-20261102:';
const ISIN='DE000A0JBPG2';
const DISPLAY_NAME='PNE AG';
const ASSET_ID='528';
const SOURCE_ID='209';
const ROUTE_ID='537';
const ROUTE_REVISION='1';
const EXPECTED_COUNTS=[
    'm2_market_observations'=>28,
    'm2_market_current'=>5,
    'm2_fundamental_observations'=>99,
    'm2_fundamental_current'=>50,
];

require_once __DIR__.'/actions_acceptance.php';
require_once __DIR__.'/tradegate_manifest.php';
require_once __DIR__.'/../market_current/refresh.php';

function privateManifest(string $root,array $manifest): string {
    check(is_dir($root)&&!is_link($root),'private_root');
    $dir=$root.'/pne-tradegate-'.hash('sha256',ISIN);check(mkdir($dir,0700),'private_directory');
    $file=$dir.'/live-manifest.json';$handle=fopen($file,'x');check($handle!==false,'private_manifest');
    try{$wire=json_encode($manifest,JSON_THROW_ON_ERROR);same(fwrite($handle,$wire),strlen($wire),'private_manifest_write');}
    finally{fclose($handle);}
    check(chmod($file,0600),'private_manifest_mode');return $dir;
}

function capture(callable $connect,array $contract): array {
    $db=$connect();$db->exec('SET TRANSACTION READ ONLY');check($db->beginTransaction(),'preflight_transaction');
    try{return \Mosa2\MarketLive\snapshot($db,$contract);}finally{if($db->inTransaction())$db->rollBack();$db=null;}
}

function countCheck(array $state): void {
    foreach(EXPECTED_COUNTS as $table=>$expected)same(count($state[$table]??[]),$expected,'protected_count_'.$table);
    same(count($state['m2_market_bars']??[]),0,'protected_count_m2_market_bars');
}

function targetScope(array $state): array {
    $ids=array_values(array_filter($state['m2_asset_identifiers'],static fn($r)=>
        $r['identifier_type']==='isin'&&$r['normalized_value']===ISIN&&$r['scope_key']===''));
    same(count($ids),1,'pne_identity');same($ids[0]['asset_id'],ASSET_ID,'pne_asset_id');
    $assets=array_values(array_filter($state['m2_assets'],static fn($r)=>$r['entity_id']===ASSET_ID));
    $entities=array_values(array_filter($state['m2_entities'],static fn($r)=>$r['id']===ASSET_ID));
    same(count($assets),1,'pne_asset');same(count($entities),1,'pne_entity');
    same($assets[0]['display_name'],DISPLAY_NAME,'pne_display_name');same($assets[0]['asset_class'],'equity','pne_asset_class');
    $sources=array_values(array_filter($state['m2_sources'],static fn($r)=>$r['source_key']==='provider:tradegate_bsx_mid'));
    same(count($sources),1,'pne_source');same($sources[0]['id'],SOURCE_ID,'pne_source_id');
    same($sources[0]['source_type'],'market_data','pne_source_type');same($sources[0]['enabled'],'1','pne_source_enabled');
    $routes=array_values(array_filter($state['m2_asset_source_routes'],static fn($r)=>
        $r['id']===ROUTE_ID&&$r['asset_id']===ASSET_ID&&$r['source_id']===SOURCE_ID&&$r['route_type']==='quote'));
    same(count($routes),1,'pne_route');$route=$routes[0];same($route['route_revision'],ROUTE_REVISION,'pne_route_revision');
    same($route['priority'],'0','pne_route_priority');same($route['enabled'],'0','pne_route_disabled');
    same($route['unit_contract_version'],'mosa2-market-unit-v1','pne_route_unit_contract');
    same($route['quote_unit_key'],'EUR','pne_route_quote_unit');same($route['quote_unit_version'],'1','pne_route_quote_version');
    foreach(['quantity_basis_unit_key','quantity_basis_unit_version','quantity_basis_amount','volume_unit_key','volume_unit_version'] as $field)
        same($route[$field],null,'pne_snapshot_unit_'.$field);
    $current=array_values(array_filter($state['m2_market_current'],static fn($r)=>$r['asset_id']===ASSET_ID));
    check(count($current)<=1,'pne_current_ambiguous');
    if($current!==[])same($current[0]['route_id'],ROUTE_ID,'pne_current_route_transition');
    return ['asset'=>$assets[0],'entity'=>$entities[0],'source'=>$sources[0],'route'=>$route,'current'=>$current[0]??null];
}

function preserveAfterObservation(array $before,array $after,array $writer): void {
    $inserted=(($writer['writer']??null)==='INSERT');
    foreach($before as $table=>$rows){
        if($table==='m2_market_observations'){
            same(count($after[$table]),count($rows)+($inserted?1:0),'observation_count_after');
            $old=[];foreach($rows as $row)$old[$row['id']]=$row;
            foreach($after[$table] as $row)if(isset($old[$row['id']]))same($row,$old[$row['id']],'old_observation_changed');
        }else same($after[$table],$rows,'protected_table_changed');
    }
}

function finalReadback(array $afterObservation,array $final,string $assetId): void {
    foreach($afterObservation as $table=>$rows){
        if($table!=='m2_market_current')same($final[$table],$rows,'final_protected_table_changed');
        else{
            $old=array_values(array_filter($rows,static fn($r)=>$r['asset_id']!==$assetId));
            $new=array_values(array_filter($final[$table],static fn($r)=>$r['asset_id']!==$assetId));
            same($new,$old,'other_current_changed');
        }
    }
}

function currentReadback(array $afterObservation,array $final,string $assetId,?string $observationId,?string $decision): void {
    $before=array_values(array_filter($afterObservation['m2_market_current'],static fn($r)=>$r['asset_id']===$assetId));
    $after=array_values(array_filter($final['m2_market_current'],static fn($r)=>$r['asset_id']===$assetId));
    check(count($after)<=1,'pne_current_readback_ambiguous');
    if(in_array($decision,['INSERT','UPDATE'],true)){
        same(count($after),1,'pne_current_missing_after_write');same($after[0]['observation_id'],$observationId,'pne_current_observation');
        same($after[0]['source_id'],SOURCE_ID,'pne_current_source');same($after[0]['route_id'],ROUTE_ID,'pne_current_route');
    }else same($after,$before,'pne_current_preserved');
}

function safeFailure(Throwable $error): string {
    return $error instanceof \PDOException?'DATABASE_OPERATION_FAILED':
        (preg_match('/^[a-z0-9_]+$/D',$error->getMessage())===1?$error->getMessage():'CONTRACT_CHECK_FAILED');
}

function run(array $input): array {
    $report=['ok'=>false,'stage'=>'initialization','provider_requests'=>0,'database_connections'=>0,'database_writes'=>0,
        'observation'=>'NOT_STARTED','current'=>'NOT_STARTED','readback'=>'NOT_STARTED','provider_gets'=>0];
    $password=null;$initial=null;$afterObservation=null;$connect=null;$private=null;
    try{
        check(($input['scope']??null)==='pne_tradegate','scope');
        $commit=$input['commit']??'';check(is_string($commit)&&preg_match('/\A[0-9a-f]{40}\z/D',$commit)===1,'commit');
        same($input['authorization']??null,AUTHORIZATION_PREFIX.$commit,'authorization');
        $password=$input['password']??null;check(is_string($password)&&$password!=='','db_secret');
        $config=$input['config']??[];same($config['state_contract']['schema_version']??null,6,'schema6_contract');
        same($config['state_contract']['allow_current']??null,true,'current_contract');
        $connect=static fn()=>connection($password,$config['db_host'],$config['db_port']);
        $report['stage']='preflight';$report['database_connections']++;$db=$connect();$db->exec('SET TRANSACTION READ ONLY');check($db->beginTransaction(),'preflight_transaction');
        try{$initial=\Mosa2\MarketLive\snapshot($db,$config['state_contract']);countCheck($initial);$scope=targetScope($initial);
            $report['before_counts']=array_map('count',$initial);}
        finally{if($db->inTransaction())$db->rollBack();$db=null;}
        $manifest=\Mosa2\TradegateQuote\manifest($initial,['isin'=>ISIN,'name'=>DISPLAY_NAME]);
        same($manifest['policy'],'USE_EXISTING_ROUTE','pne_existing_route');same($manifest['instrument'],ISIN,'pne_manifest_instrument');
        same($manifest['provider_key'],'tradegate_bsx_quote_v1','pne_manifest_provider');same($manifest['adapter_class'],'TradegateQuoteV1','pne_manifest_adapter');
        $plan=\Mosa2\MarketLive\completePlan($initial,$manifest);same($plan['route']['decision'],'EXISTING_MATCH','pne_route_plan');
        same($plan['route']['route_id']??null,ROUTE_ID,'pne_plan_route_id');$private=privateManifest($input['private_root'],$manifest);
        $gate=static function(array $runtimeConfig)use($input): void{
            same($runtimeConfig['state_contract']['schema_version']??null,6,'schema6_one_shot_contract');
            same($runtimeConfig['one_shot_scope']??null,'PNE_TRADEGATE','schema6_one_shot_scope');
            same($runtimeConfig['one_shot_authorization']??null,$input['authorization'],'schema6_one_shot_authorization');
        };
        $report['stage']='provider_and_observation';$proof=\Mosa2\MarketLive\proofRun($private,$password,$config,$manifest,$gate);
        $report['provider_requests']=$proof['provider_requests']??0;$report['provider_gets']=$report['provider_requests'];
        $report['database_connections']+=(int)($proof['database_connections']??0);$report['observation']=$proof['writer']??'FAILED';
        $report['observation_id']=$proof['observation_id']??null;check(($proof['ok']??false)===true,'observation_failed');
        $afterObservation=capture($connect,$config['state_contract']);$report['database_connections']++;preserveAfterObservation($initial,$afterObservation,$proof);
        $report['observation_delta']=($proof['writer']??null)==='INSERT'?1:0;$report['database_writes']=$report['observation_delta'];
        if($report['observation_delta']===1){
            $route=$scope['route'];$approvalNow=gmdate('Y-m-d H:i:s').'.000000';
            $approval=['route_id'=>$route['id'],'route_sha256'=>hash('sha256',\Mosa2\Phase3D\json($route)),'approved_at'=>$approvalNow,'allow_disabled_projection'=>true];
            $currentConfig=$config+['project'=>dirname(__DIR__,2),'python'=>$config['python']];
            $report['stage']='current_projection';$current=\Mosa2\MarketCurrent\refresh($password,$currentConfig,[$approval]);
            $report['database_connections']+=2;$report['current_decision']=$current['decisions'][0]??null;$report['current']=$report['current_decision']??'UNKNOWN';
            $report['database_writes']+=in_array($report['current_decision'],['INSERT','UPDATE'],true)?1:0;
        }else{$report['current']='UNCHANGED_DUPLICATE';$report['current_decision']='UNCHANGED_DUPLICATE';}
        $final=capture($connect,$config['state_contract']);$report['database_connections']++;$report['after_counts']=array_map('count',$final);
        finalReadback($afterObservation,$final,ASSET_ID);
        currentReadback($afterObservation,$final,ASSET_ID,$report['observation_id']??null,$report['current_decision']??null);
        $report['stage']='complete';$report['readback']='PASS';$report['ok']=true;
    }catch(Throwable $error){$report['failure_phase']=$report['stage'];$report['failure_code']=safeFailure($error);}
    finally{unset($password,$connect);}
    return $report;
}

function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{
        $input=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
        $report=run($input);echo json_encode($report,JSON_THROW_ON_ERROR);
    }catch(Throwable){echo json_encode(['ok'=>false,'stage'=>'initialization','failure_phase'=>'initialization','failure_code'=>'INVALID_RUNNER_INPUT'],JSON_THROW_ON_ERROR);}
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)main();
