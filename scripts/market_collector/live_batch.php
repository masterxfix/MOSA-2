<?php
declare(strict_types=1);
namespace Mosa2\MarketBatch;
use Throwable;
use function Mosa2\Phase2\{check,same};
require_once __DIR__.'/live_persistence.php';

const CONTRACT='mosa2-manual-live-batch-v2';
/** Explicit common adapter registry, independent of assets and physical IDs. */
function providers(): array {
    require_once __DIR__.'/tradegate_manifest.php';
    require_once __DIR__.'/actions_acceptance.php';
    return ['provider:tradegate_bsx_mid'=>'Mosa2\\TradegateQuote\\manifest',
        'provider:boerse_frankfurt_api'=>'Mosa2\\MarketAcceptance\\manifest',
        'provider:gettex_mund_delayed'=>'Mosa2\\MarketAcceptance\\gettexManifest'];
}
/** Registry qualification belongs to the shared planning library. */
function qualify(array $state,array $selection,callable $manifestFactory): array {
    return \Mosa2\MarketLive\qualifyBatch($state,$selection,$manifestFactory);
}
function path(string $value): string {
    $resolved=realpath($value);check(is_string($resolved)&&is_dir($resolved)&&!is_link($value),'batch_directory');
    $canonical=str_replace('\\','/',$resolved);same(str_replace('\\','/',$value),$canonical,'batch_canonical_path');return $canonical;
}
function inside(string $child,string $parent): bool {return $child===$parent||str_starts_with($child,$parent.'/');}
/** Validate the complete explicit scope before I/O; preserve configured order. */
function prepare(string $privateRoot,string $publicRoot,array $entries): array {
    check(array_is_list($entries)&&count($entries)>=1&&count($entries)<=10,'batch_size');
    $root=path($privateRoot);$web=path($publicRoot);check(!inside($root,$web),'batch_private_root');$prepared=[];$identities=[];$folders=[];
    foreach($entries as $entry){
        check(is_array($entry)&&array_keys($entry)===['private_root']&&is_string($entry['private_root']),'batch_entry');
        $folder=path($entry['private_root']);check($folder!==$root&&inside($folder,$root)&&!inside($folder,$web),'batch_item_root');
        $ancestor=$folder;while($ancestor!==$root){check(!is_link($ancestor),'batch_symlink');$ancestor=str_replace('\\','/',dirname($ancestor));}
        check(!isset($folders[$folder]),'batch_duplicate_folder');$folders[$folder]=true;
        $file=$folder.'/live-manifest.json';check(is_file($file)&&!is_link($file),'batch_manifest');
        $manifest=json_decode(file_get_contents($file),true,64,JSON_THROW_ON_ERROR);
        same($manifest['policy']??null,'USE_EXISTING_ROUTE','batch_policy');
        $identity=\Mosa2\MarketIdentity\qualifiedIdentity($manifest['identity']);
        $key=\Mosa2\MarketIdentity\identifierKey($identity);ksort($key,SORT_STRING);$key=\Mosa2\Phase3D\json($key);
        check(!isset($identities[$key]),'batch_duplicate_identifier');$identities[$key]=true;
        $prepared[]=['key'=>$key,'fingerprint'=>hash('sha256',$key),'private_root'=>$folder,'manifest'=>$manifest];
    }
    return $prepared;
}
function counter(mixed $value): ?int {return is_int($value)&&$value>=0?$value:null;}
function total(?int $sum,?int $value): ?int {return $sum===null||$value===null?null:$sum+$value;}

/** One general catalog -> qualification -> batch -> Current path, with injectable I/O. */
function collect(string $root,string $password,array $config,array $scope,?callable $connect=null,?callable $invoke=null,?callable $refresh=null): array {
    require_once __DIR__.'/batch_scope.php';
    require_once __DIR__.'/actions_acceptance.php';
    require_once __DIR__.'/../market_current/refresh.php';
    $connect??=static fn()=>\Mosa2\Phase2\connection($password,$config['db_host']??'127.0.0.1',$config['db_port']??3307);
    $invoke??='Mosa2\\MarketLive\\bridge';
    $refresh??=static fn($approvals)=>\Mosa2\MarketCurrent\refresh($password,$config,$approvals);
    $report=['ok'=>false,'stage'=>'qualification','provider_requests'=>0,'batch'=>null,'current'=>null];$initial=null;
    try{
        check(in_array($scope['mode']??null,['manual','automatic'],true),'collection_mode');
        $manual=$scope['mode']==='manual';
        check(is_int($scope['request_budget']??null)&&$scope['request_budget']>=1&&$scope['request_budget']<=10,'collection_budget');
        $initial=\Mosa2\MarketAcceptance\capture($connect,$config['state_contract']);
        $selection=\Mosa2\MarketBatchScope\selection($initial,gmdate('Y-m-d H:i:s').'.000000');
        $plan=\Mosa2\MarketBatchScope\plan($initial,$selection,$scope['source_priority'],providers(),
            'Mosa2\\MarketLive\\completePlan',$manual,10,$scope['expected_isins']??null);
        // Physical IDs and their hashes bind the entire reviewed scope before any GET.
        $routes=[];$approvals=[];
        foreach($plan['prepared'] as $item){
            $route=array_values(array_filter($initial['m2_asset_source_routes'],static fn($r)=>$r['id']===$item['route_id']));
            same(count($route),1,'collection_route');$routes[$item['route_id']]=hash('sha256',\Mosa2\Phase3D\json($route[0]));
            $approval=['route_id'=>$item['route_id'],'route_sha256'=>$routes[$item['route_id']],
                'approved_at'=>gmdate('Y-m-d H:i:s').'.000000','allow_disabled_projection'=>$manual];
            $old=array_values(array_filter($initial['m2_market_current'],static fn($r)=>$r['asset_id']===$item['asset_id']));
            if(count($old)===1&&$old[0]['route_id']!==$item['route_id']){
                $previous=array_values(array_filter($initial['m2_asset_source_routes'],static fn($r)=>$r['id']===$old[0]['route_id']));
                same(count($previous),1,'collection_previous_route');
                $approval+=['allow_route_transition'=>true,'previous_route_sha256'=>hash('sha256',\Mosa2\Phase3D\json($previous[0]))];
            }
            $approvals[]=$approval;
        }
        check(count($routes)>0&&count($routes)<=$scope['request_budget'],'collection_budget');
        same($scope['routes']??null,$routes,'collection_authorized_routes');
        $entries=[];
        foreach($plan['prepared'] as $item)$entries[]=['private_root'=>\Mosa2\MarketAcceptance\privateItem($root,'batch',$item['manifest'])];
        $prepared=prepare($root,$config['public_root'],$entries);
        $gate=static function($c,$baseline,$decided)use($manual,$routes){
            $id=$decided['route']['route_id'];
            $physical=array_values(array_filter($baseline['m2_asset_source_routes'],static fn($r)=>$r['id']===$id));
            same(count($physical),1,'collection_route_drift');
            same(hash('sha256',\Mosa2\Phase3D\json($physical[0])),$routes[$id]??null,'collection_route_drift');
            if(!$manual)\Mosa2\CollectorSchema5\acquisitionAllowed($c['state_contract']);
            else check(in_array($c['state_contract']['schema_version'],[4,5,6],true),'collection_schema');
        };
        $config['allow_duplicate']=true;$report['stage']='batch';
        $batch=execute($prepared,static fn($entry)=>\Mosa2\MarketLive\proofRun($entry['private_root'],$password,$config,$entry['manifest'],$gate,$connect,$invoke));
        $report['provider_requests']=$batch['provider_requests'];$report['batch']=$batch;
        unset($report['batch']['private_evidence']);
        check($batch['overall_status']==='COMPLETE','collection_batch_incomplete');
        $report['stage']='current';$report['current']=$refresh($approvals);
        check(($report['current']['readback']??null)==='PASS','collection_current_readback');
        unset($report['current']['private_evidence']);
        $report['stage']='readback';$after=\Mosa2\MarketAcceptance\capture($connect,$config['state_contract']);
        foreach($initial as $table=>$rows){
            if(!in_array($table,['m2_market_current','m2_market_observations'],true))same($after[$table],$rows,'collection_protected_data');
        }
        $selected=array_column($plan['prepared'],'asset_id');
        same(array_values(array_filter($after['m2_market_current'],static fn($r)=>!in_array($r['asset_id'],$selected,true))),
            array_values(array_filter($initial['m2_market_current'],static fn($r)=>!in_array($r['asset_id'],$selected,true))),'collection_other_current');
        $report['after_counts']=array_map('count',$after);$report['protection']='PASS';$report['ok']=true;$report['stage']='complete';
    }catch(Throwable $e){$report['failure']=$e instanceof \PDOException?'database_operation_failed':$e->getMessage();}
    finally{
        if($initial!==null){
            try{
                $final=\Mosa2\MarketAcceptance\capture($connect,$config['state_contract']);
                $report['before_counts']=array_map('count',$initial);$report['after_counts']=array_map('count',$final);
                $report['database_writes']=count($final['m2_market_observations'])-count($initial['m2_market_observations']);
                foreach($final['m2_market_current'] as $row){
                    $old=array_values(array_filter($initial['m2_market_current'],static fn($r)=>$r['asset_id']===$row['asset_id']));
                    if($old===[]||$old[0]!==$row)$report['database_writes']++;
                }
                $report['stored_current']=$final['m2_market_current'];
                foreach($initial as $table=>$rows)if(!in_array($table,['m2_market_current','m2_market_observations'],true))same($final[$table],$rows,'collection_protected_data');
                $report['protection']='PASS';
            }catch(Throwable){$report['ok']=false;$report['final_readback']='FAIL';$report['database_writes']=null;$report['protection']='UNCONFIRMED';}
        }
        unset($password);
    }
    return $report;
}
/** Pure sequential coordination; injected runners are used by offline tests. */
function execute(array $prepared,callable $runner): array {
    check(array_is_list($prepared)&&count($prepared)>=1&&count($prepared)<=10,'batch_size');
    $seen=[];foreach($prepared as $entry){$key=$entry['key'];check(!isset($seen[$key]),'batch_duplicate_identifier');$seen[$key]=true;}
    $report=['contract_version'=>CONTRACT,'started_count'=>0,'completed_count'=>0,'failed_count'=>0,'not_started_count'=>count($prepared),
        'committed_count'=>0,'provider_requests'=>0,'database_connections'=>0,'item_results'=>[],'overall_status'=>'FAILED_BEFORE_FIRST_COMMIT'];$private=[];
    foreach($prepared as $i=>$entry)$report['item_results'][]=['position'=>$i+1,'asset_identity'=>$entry['manifest']['identity']['normalized_value'],
        'status'=>'NOT_STARTED','provider_request_performed'=>false,'committed'=>false,'writer'=>null,'observation_id'=>null,'replay'=>null,'failure_stage'=>null];
    foreach($prepared as $i=>$entry){
        $report['started_count']++;$report['not_started_count']--;
        try{$result=$runner($entry);check(is_array($result),'batch_runner_result');}
        catch(Throwable){$result=['ok'=>false,'committed'=>null,'provider_requests'=>null,'database_connections'=>null,'failure'=>'runner_exception'];}
        $success=($result['ok']??false)===true&&($result['committed']??false)===true;
        $item=['position'=>$i+1,'status'=>$success?'COMPLETE':'FAILED','committed'=>$result['committed']??null,
            'provider_requests'=>counter($result['provider_requests']??null),'database_connections'=>counter($result['database_connections']??null)];
        $item+=['asset_identity'=>$entry['manifest']['identity']['normalized_value'],'provider_request_performed'=>$item['provider_requests']===null?null:$item['provider_requests']>0,
            'writer'=>null,'observation_id'=>$result['observation_id']??null,'replay'=>null,'failure_stage'=>$success?null:($result['stage']??'runner')];
        foreach(['policy','asset_plan','route_plan','writer','replay','readback','deltas','metrics','provider_duration_ms'] as $field)if(array_key_exists($field,$result))$item[$field]=$result[$field];
        $item['source']=$result['private_evidence']['plan']['source']['decision']??null;
        if(!$success)$item['failure_code']=preg_match('/\A[a-z0-9_]+\z/D',$result['failure']??'')===1?$result['failure']:'item_failed';
        $report['item_results'][$i]=$item;$private[]=['position'=>$i+1,'fingerprint'=>$entry['fingerprint'],'result'=>$result];
        foreach(['provider_requests','database_connections'] as $field)$report[$field]=total($report[$field],$item[$field]);
        if($item['committed']===true)$report['committed_count']++;
        if(!$success){$report['failed_count']++;break;}$report['completed_count']++;
    }
    $report['overall_status']=$report['completed_count']===count($prepared)?'COMPLETE':($report['committed_count']>0?'PARTIAL_FAILED':'FAILED_BEFORE_FIRST_COMMIT');
    $report['private_evidence']=['items'=>$private];return $report;
}
function run(string $privateRoot,string $password,array $config,array $entries): array {
    try {
        try{$prepared=prepare($privateRoot,$config['public_root'],$entries);}
        catch(Throwable){return ['contract_version'=>CONTRACT,'started_count'=>0,'completed_count'=>0,'failed_count'=>0,'not_started_count'=>count($entries),
            'provider_requests'=>0,'database_connections'=>0,'item_results'=>array_map(static fn($i)=>['position'=>$i+1,'status'=>'NOT_STARTED','asset_identity'=>null,
                'provider_request_performed'=>false,'committed'=>false,'writer'=>null,'observation_id'=>null,'replay'=>null,'failure_stage'=>'batch_validation'],array_keys(array_values($entries))),
            'committed_count'=>0,'overall_status'=>'FAILED_BEFORE_FIRST_COMMIT','failure'=>'batch_validation'];}
        return execute($prepared,static fn($entry)=>\Mosa2\MarketLive\run($entry['private_root'],$password,$config,$entry['manifest']));
    }finally{unset($password);}
}

/** Stdin-only manual Actions entry; scope is reviewed as ISINs, never fixture IDs. */
if(realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    $started=false;
    try{
        require_once __DIR__.'/batch_scope.php';require_once __DIR__.'/actions_acceptance.php';
        $input=json_decode(stream_get_contents(STDIN),true,64,JSON_THROW_ON_ERROR);
        $config=$input['config'];$password=$input['password'];$scope=$input['scope'];
        check($scope['mode']==='manual'&&is_int($scope['request_budget'])&&$scope['request_budget']>=1&&$scope['request_budget']<=5,'manual_request_budget');
        $connect=static fn()=>\Mosa2\Phase2\connection($password,$config['db_host'],$config['db_port']);
        $state=\Mosa2\MarketAcceptance\capture($connect,$config['state_contract']);
        $selection=\Mosa2\MarketBatchScope\selection($state,gmdate('Y-m-d H:i:s').'.000000');
        $plan=\Mosa2\MarketBatchScope\plan($state,$selection,$scope['source_priority'],providers(),'Mosa2\\MarketLive\\completePlan',true,10,$scope['expected_isins']);
        $actual=array_column($plan['prepared'],'isin');$expected=$scope['expected_isins'];sort($actual);sort($expected);
        same($actual,$expected,'manual_asset_scope');check(count($actual)===count(array_unique($actual)),'manual_duplicate_scope');
        $scope['routes']=[];
        foreach($plan['prepared'] as $item){$route=array_values(array_filter($state['m2_asset_source_routes'],static fn($r)=>$r['id']===$item['route_id']))[0];$scope['routes'][$item['route_id']]=hash('sha256',\Mosa2\Phase3D\json($route));}
        $started=true;$result=collect($input['private_root'],$password,$config,$scope);
        unset($password,$input,$connect);
        echo json_encode($result,JSON_THROW_ON_ERROR);exit($result['ok']?0:1);
    }catch(Throwable){echo json_encode(['ok'=>false,'failure'=>$started?'collection_result_unknown':'collection_preflight_failed',
        'provider_requests'=>$started?null:0,'database_writes'=>$started?null:0]);exit(1);}
}
