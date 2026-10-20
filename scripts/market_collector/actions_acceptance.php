<?php
declare(strict_types=1);
namespace Mosa2\MarketAcceptance;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,connection};
use function Mosa2\MarketLive\{snapshot,completePlan,bridge,strings,compareDelta};
use function Mosa2\MarketIdentity\{planAssetIdentity,planMarketRoute,applyAssetIdentityPlan,applyMarketRoutePlan};
require_once __DIR__.'/live_batch.php';

/** Generic manifest generation from authenticated catalog identity, not numeric fixture IDs.
 * Route identity uses the historical Phase-3D ISIN+venue contract (not ISIN+MIC).
 * Exact legacy hashes remain checked by the unchanged route planner.
 */
function manifest(array $state,array $selection): array {
    $isin=$selection['isin'];check(\Mosa2\Phase3D\isinValid($isin),'scope_isin');
    $ids=array_values(array_filter($state['m2_asset_identifiers'],static fn($r)=>$r['identifier_type']==='isin'&&$r['normalized_value']===$isin&&$r['scope_key']===''));
    same(count($ids),1,'scope_global_identity');$id=$ids[0]['asset_id'];
    $assets=array_values(array_filter($state['m2_assets'],static fn($r)=>$r['entity_id']===$id));
    $entities=array_values(array_filter($state['m2_entities'],static fn($r)=>$r['id']===$id));
    same(count($assets),1,'scope_asset');same(count($entities),1,'scope_entity');
    same($assets[0]['display_name'],$selection['name'],'scope_name');
    $identity=['canonical_name'=>$entities[0]['canonical_name'],'display_name'=>$assets[0]['display_name'],'asset_class'=>$assets[0]['asset_class'],
        'identifier_type'=>'isin','identifier_value'=>$isin,'normalized_value'=>$isin,'scope_key'=>'','is_primary'=>1];
    same(planAssetIdentity($state,$identity)['decision'],'EXISTING_MATCH','scope_identity_conflict');
    $units=array_fill_keys(\Mosa2\MarketIdentity\UNIT_FIELDS,null);
    $units['unit_contract_version']='mosa2-market-unit-v1';$units['quote_unit_key']='EUR';$units['quote_unit_version']='1';
    $evidence=['sample_id'=>'LIVE-'.substr(hash('sha256',$isin),0,10),'source_reference'=>'qualified:frankfurt:'.$isin,'family'=>'frankfurt_snapshot',
        'row'=>['isin'=>$isin,'provider_key'=>'boerse_frankfurt_api','venue_key'=>'boerse_frankfurt','currency'=>'EUR','quote_variant'=>null,'series'=>'snapshot','observation_kind'=>'market_quote'],
        'proof'=>['external_identity'=>['isin'=>$isin,'venue'=>'boerse_frankfurt'],'route_reference'=>'Phase-3D ISIN+venue; FrankfurtSnapshotV1 verifies ISIN/XFRA/EUR',
            'unit_class'=>'currency_per_instrument']];
    $sources=array_values(array_filter($state['m2_sources'],static fn($r)=>$r['source_key']==='provider:boerse_frankfurt_api'));
    same(count($sources),1,'scope_source');
    $route=planMarketRoute($state['m2_asset_source_routes'],['asset_id'=>$id,'source_id'=>$sources[0]['id'],'route_type'=>'quote','priority'=>0,'enabled'=>0,'evidence'=>$evidence],$units);
    check(in_array($route['decision'],['CREATE_REVISION','EXISTING_MATCH'],true),'scope_route_conflict');
    $m=['policy'=>$route['decision']==='EXISTING_MATCH'?'USE_EXISTING_ROUTE':'ONBOARD_NEW_ROUTE','identity'=>$identity,'route_evidence'=>$evidence,'unit_binding'=>$units,
        'instrument'=>$isin,'provider_key'=>'boerse_frankfurt_api_v1','adapter_module'=>'scripts.market_collector.boerse_frankfurt','adapter_class'=>'FrankfurtSnapshotV1'];
    completePlan($state,$m);return $m;
}
function privateItem(string $root,string $kind,array $m): string {
    $dir=$root.'/'.$kind.'-'.hash('sha256',$m['instrument']);check(mkdir($dir,0700),'private_directory');
    $file=$dir.'/live-manifest.json';$f=fopen($file,'x');check($f!==false,'private_manifest');
    try{$wire=json_encode($m,JSON_THROW_ON_ERROR);same(fwrite($f,$wire),strlen($wire),'private_manifest_write');}finally{fclose($f);}
    check(chmod($file,0600),'private_manifest_mode');return $dir;
}
function capture(callable $connect,array $contract): array {
    $p=$connect();$p->exec('SET TRANSACTION READ ONLY');$p->beginTransaction();
    try{return snapshot($p,$contract);}finally{$p->rollBack();}
}
function counts(array $state): array {return array_map('count',$state);}
function acceptance(array $scope,string $root,array $config,callable $connect,callable $invoke): array {
    $r=['ok'=>false,'stage'=>'database_authentication','db_authentication'=>'NOT_CHECKED','ledger'=>'NOT_CHECKED','preparation_provider_requests'=>0,
        'qualification'=>array_map(static fn($s)=>['isin'=>$s['isin'],'status'=>$s['qualify']?'NOT_STARTED':'PREVIOUSLY_QUALIFIED'],$scope),
        'catalog_route_deltas'=>[],'batch'=>null,'current_unchanged'=>'NOT_CHECKED','bars_unchanged'=>'NOT_CHECKED','unexpected_writes'=>'NOT_CHECKED'];
    $initial=null;$expected=null;$batchBefore=null;$inserted=[];$plans=[];
    try{
        // Authentication/target validation occurs inside connection(), before any provider.
        $probe=$connect();$r['db_authentication']='PASS';$r['stage']='ledger';
        $probe->exec('SET TRANSACTION READ ONLY');$probe->beginTransaction();
        try{\Mosa2\MarketLive\runtimeContract($probe,$config['state_contract']);}
        finally{$probe->rollBack();$probe=null;}
        $r['ledger']='PASS';$r['stage']='scope_preflight';
        check(array_is_list($scope)&&count($scope)>=1&&count($scope)<=10,'scope_size');$seen=[];
        check(count(array_filter($scope,static fn($s)=>$s['qualify']===true))<=3,'qualification_budget');
        $initial=capture($connect,$config['state_contract']);$expected=$initial;$r['before_counts']=counts($initial);$manifests=[];
        foreach($scope as $s){check(!isset($seen[$s['isin']]),'scope_duplicate');$seen[$s['isin']]=true;
            $m=manifest($initial,$s);if(!$s['qualify'])same($m['policy'],'USE_EXISTING_ROUTE','previously_qualified_route');$manifests[]=$m;}
        // Validate every catalog/route plan before consuming the preparation budget.
        foreach($manifests as $m)$plans[]=completePlan($initial,$m);
        $r['stage']='qualification';
        foreach($scope as $i=>$s)if($s['qualify']){
            $dir=privateItem($root,'qualify',$manifests[$i]);$r['qualification'][$i]['status']='FAILED';
            try{$acquired=$invoke($config,['action'=>'fetch','private_root'=>$dir,'php_cli'=>$config['php']]);}
            finally{if(is_file($dir.'/provider-consumed.lock'))$r['preparation_provider_requests']++;}
            $binding=['id'=>'1','asset_id'=>$plans[$i]['asset']['asset_id'],'source_id'=>$plans[$i]['source']['source_id'],'route_revision'=>'1']+$manifests[$i]['unit_binding'];
            $proof=$invoke($config,['action'=>'qualify','acquired'=>$acquired,'route'=>$binding]);
            same($proof['currency'],'EUR','qualification_currency');same($proof['quote_unit_key'],'EUR','qualification_unit');same($proof['quote_unit_version'],'1','qualification_version');
            $r['qualification'][$i]=['isin'=>$s['isin'],'status'=>'PASS','market_at'=>$proof['market_at'],'observed_at'=>$proof['observed_at'],'scope'=>$proof['scope']];
            unset($acquired,$proof);
        }
        $r['stage']='onboarding';$p=$connect();$p->beginTransaction();
        try{
            same(snapshot($p,$config['state_contract']),$initial,'onboarding_baseline_drift');
            $store=new \Mosa2\MarketIdentity\PdoStore($p);$now=gmdate('Y-m-d H:i:s').'.000000';$delta=array_fill_keys(array_keys($initial),0);
            foreach($manifests as $i=>$m){
                same(completePlan(snapshot($p,$config['state_contract']),$m),$plans[$i],'onboarding_plan_drift');
                $asset=applyAssetIdentityPlan($store,$plans[$i]['asset'],$now);
                $row=strings(applyMarketRoutePlan($store,$plans[$i]['route'],$asset['asset_id'],$now));
                if($plans[$i]['route']['decision']==='CREATE_REVISION'){$inserted['m2_asset_source_routes'][]=$row;$expected['m2_asset_source_routes'][]=$row;$delta['m2_asset_source_routes']++;}
            }
            same(snapshot($p,$config['state_contract']),$expected,'onboarding_exact_delta');same($p->commit(),true,'onboarding_commit');
            $r['catalog_route_deltas']=$delta;
        }catch(Throwable $e){if($p->inTransaction())$p->rollBack();$expected=$initial;throw $e;}finally{$p=null;}
        $r['stage']='onboarding_readback';same(capture($connect,$config['state_contract']),$expected,'onboarding_independent_readback');
        $r['stage']='final_preflight';$entries=[];
        foreach($manifests as &$m){$m['policy']='USE_EXISTING_ROUTE';completePlan($expected,$m);$entries[]=['private_root'=>privateItem($root,'final',$m)];}unset($m);
        $prepared=\Mosa2\MarketBatch\prepare($root,$config['public_root'],$entries);$batchBefore=$expected;
        // Exclusive marker is outside all asset folders; no final batch can be invoked twice.
        $lock=fopen($root.'/final-batch-started.lock','x');check($lock!==false,'final_batch_already_started');fclose($lock);
        $r['stage']='batch';$r['batch']=\Mosa2\MarketBatch\execute($prepared,static function($entry)use($connect,$invoke,$config){
            $started=hrtime(true);$result=\Mosa2\MarketLive\runtimeRun($entry['private_root'],$config,$entry['manifest'],$connect,$invoke);
            $result['provider_requests']=is_file($entry['private_root'].'/provider-consumed.lock')?1:0;
            $result['metrics']=['duration_ms'=>(hrtime(true)-$started)/1e6,'provider_duration_ms'=>$result['provider_duration_ms']??null,'sql_calls'=>null,'returned_rows'=>null];return $result;
        });unset($r['batch']['private_evidence']);
        $r['stage']='final_readback';$after=capture($connect,$config['state_contract']);$observationDelta=0;
        foreach($r['batch']['item_results'] as $item)if($item['committed']===true&&$item['writer']==='INSERT'){
            $rows=array_values(array_filter($after['m2_market_observations'],static fn($row)=>$row['id']===$item['observation_id']));same(count($rows),1,'committed_observation');
            $inserted['m2_market_observations'][]=$rows[0];$observationDelta++;
        }
        $delta=['m2_asset_source_routes'=>count($inserted['m2_asset_source_routes']??[]),'m2_market_observations'=>$observationDelta];
        compareDelta($initial,$after,['deltas'=>$delta],$inserted);$expected=$after;
        $r['unexpected_writes']='PASS';$r['after_counts']=counts($after);$r['observation_delta']=$observationDelta;
        $r['ok']=$r['batch']['overall_status']==='COMPLETE';$r['stage']='complete';
    }catch(Throwable $e){
        // No PDO/provider/subprocess exception text is published.
        $r['failure_type']=$e instanceof \PDOException?'DATABASE_OPERATION_FAILED':get_class($e);
        $codes=['target_identity','runtime_endpoint','runtime_or_secret','scope_global_identity','scope_asset','scope_entity','scope_name','scope_identity_conflict','scope_route_conflict','scope_source','previously_qualified_route','qualification_budget','bridge_fetch','bridge_qualify','onboarding_baseline_drift','onboarding_plan_drift','onboarding_exact_delta','onboarding_independent_readback'];
        $r['failure_code']=in_array($e->getMessage(),$codes,true)?$e->getMessage():'CONTRACT_CHECK_FAILED';
        if($e instanceof \PDOException)$r['mysql_error_code']=(int)($e->errorInfo[1]??0);
    }finally{
        if($initial!==null){
            try{$after=capture($connect,$config['state_contract']);$r['after_counts']=counts($after);
                foreach(['current'=>'m2_market_current','bars'=>'m2_market_bars'] as $label=>$t)$r[$label.'_unchanged']=$after[$t]===$initial[$t]?'PASS':'FAIL';
                if($r['current_unchanged']!=='PASS'||$r['bars_unchanged']!=='PASS')$r['ok']=false;
                if($r['batch']===null&&$expected!==null){same($after,$expected,'early_stop_state');$r['unexpected_writes']='PASS';}
            }catch(Throwable){$r['integrity_readback']='FAIL';$r['ok']=false;}
        }
    }
    return $r;
}
function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{
        $in=json_decode(stream_get_contents(STDIN),true,32,JSON_THROW_ON_ERROR);$password=$in['password'];
        $config=$in['config'];$connect=static fn()=>connection($password,$config['db_host'],$config['db_port']);
        $scope=json_decode(file_get_contents(__DIR__.'/live_test_scope.json'),true,32,JSON_THROW_ON_ERROR);
        $r=acceptance($scope,$in['private_root'],$config,$connect,'Mosa2\\MarketLive\\bridge');unset($password,$in,$connect);
        echo json_encode($r,JSON_THROW_ON_ERROR);
    }catch(Throwable){echo json_encode(['ok'=>false,'stage'=>'initialization','failure_type'=>'INVALID_RUNNER_INPUT']);}
}
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)main();
