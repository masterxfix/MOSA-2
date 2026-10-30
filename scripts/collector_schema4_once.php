<?php
declare(strict_types=1);
namespace Mosa2\Schema4Once;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,connection};
require_once __DIR__.'/market_current/refresh.php';
require_once __DIR__.'/market_collector/actions_acceptance.php';
require_once dirname(__DIR__).'/api/current_read.php';
require_once __DIR__.'/collector_release/runtime.php';

const ROOT='/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector';
const WEB='/var/www/vhosts/web213.server10.configcenter.info/mosa2-test.scharwerk.de';
const AUTHORIZATION='MOSA2-SCHEMA4-ONE-SHOT-20261030:';

function stamp(): string {return (new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');}
function canonical(array $value): string {return \Mosa2\ObservationRead\canonical($value);}
function save(string $path,array $value): void {
    $f=fopen($path,'x');check(is_resource($f),'once_file_exists');
    try{$raw=json_encode($value,JSON_THROW_ON_ERROR);same(fwrite($f,$raw),strlen($raw),'once_write');check(fflush($f)&&fsync($f),'once_fsync');}
    finally{fclose($f);}
}
/** The validated publication boundary supplies candidates; a registry entry alone cannot qualify. */
function choose(array $published): array {
    $candidates=[];
    foreach($published as $entry){$r=$entry['route'];
        if($r['asset_class']==='equity'&&$r['source_key']==='provider:boerse_frankfurt_api'
            &&$r['quote_unit_key']==='EUR'&&$r['quote_unit_version']==='1')$candidates[]=$entry;
    }
    check(count($candidates)>0,'once_no_published_equity');
    usort($candidates,static fn($a,$b)=>strcmp($a['route']['isin'],$b['route']['isin']));
    return $candidates[0];
}
/** The same byte contract as MarketCurrent.planner.route_hash; never enable the route. */
function approval(array $route,string $now): array {
    return ['route_id'=>$route['id'],'route_sha256'=>hash('sha256',canonical($route)),
        'approved_at'=>$now,'allow_disabled_projection'=>true];
}
/** Full before/after proof is explicit to this one-asset acceptance, not a new runtime path. */
function unchanged(array $before,array $after,array $scope): void {
    foreach($before as $table=>$rows){
        if($table==='m2_market_observations'){
            $old=array_column($rows,'id');$added=[];$kept=[];
            foreach($after[$table] as $r){if(in_array($r['id'],$old,true))$kept[]=$r;else $added[]=$r;}
            same($kept,$rows,'once_old_observations_changed');check(count($added)<=1,'once_observation_budget');
            foreach($added as $r)foreach(['asset_id','source_id','route_id'] as $k)same($r[$k],$scope[$k],'once_observation_scope');
        }elseif($table==='m2_market_current'){
            $other=static fn($r)=>$r['asset_id']!==$scope['asset_id'];
            same(array_values(array_filter($after[$table],$other)),array_values(array_filter($rows,$other)),'once_other_current_changed');
            same(count($after[$table]),count($rows),'once_current_scope');
        }else same($after[$table],$rows,'once_unplanned_business_write');
    }
}
function run(array $in,string $project): array {
    $commit=$in['commit']??'';$run=$in['run']??'';
    check(is_string($commit)&&preg_match('/^[a-f0-9]{40}$/D',$commit)===1,'once_commit');
    same($project,ROOT.'/releases/'.$commit,'once_release');same(realpath($project),$project,'once_release_path');
    same($in['authorization']??null,AUTHORIZATION.$commit,'once_authorization');
    check(is_string($run)&&preg_match('/^schema4-[a-f0-9]{40}-[1-9][0-9]{0,19}$/D',$run)===1,'once_run');
    check(str_starts_with($run,'schema4-'.$commit.'-'),'once_run_binding');
    $root=ROOT.'/runs/'.$run;same(realpath($root),$root,'once_run_path');
    check(!is_link($root)&&fileowner($root)===10317&&filegroup($root)===1003&&(fileperms($root)&0777)===0700,'once_run_metadata');
    $password=$in['password'];check(is_string($password)&&$password!=='','once_secret');
    $config=\Mosa2\CollectorRelease\configuration($project,4);
    $config['state_contract']=['schema_version'=>4,'allow_current'=>true];$config['public_root']=WEB;
    $p=connection($password);$p->exec('SET SESSION max_execution_time=10000');
    $p->exec('SET TRANSACTION READ ONLY');check($p->beginTransaction(),'once_preflight');
    try{
        $before=\Mosa2\MarketLive\snapshot($p,$config['state_contract']);
        foreach($before as $rows)check(count($rows)<=10000,'once_test_state_bound');
        $selected=choose(\Mosa2\CurrentRead\published($p,stamp(),1800));$r=$selected['route'];
        $m=\Mosa2\MarketAcceptance\manifest($before,['isin'=>$r['isin'],'name'=>$r['display_name']]);
        same($m['policy'],'USE_EXISTING_ROUTE','once_existing_route');$plan=\Mosa2\MarketLive\completePlan($before,$m);
        same($plan['route']['route_id'],$r['route_id'],'once_display_route');
        $scope=['asset_id'=>$r['asset_id'],'source_id'=>$r['source_id'],'route_id'=>$r['route_id']];
        $route=array_values(array_filter($before['m2_asset_source_routes'],static fn($v)=>$v['id']===$r['route_id']));same(count($route),1,'once_route');
        $approvals=[approval($route[0],stamp())+['run_id'=>$run,'commit'=>$commit]];
        \Mosa2\MarketCurrent\plans($config,\Mosa2\MarketCurrent\inputs($p,$approvals,stamp()));
    }finally{if($p->inTransaction())$p->rollBack();$p=null;}
    save($root.'/preflight.json',['commit'=>$commit,'run'=>$run,'scope'=>$scope,'isin'=>$r['isin'],
        'approvals'=>$approvals,'before_sha256'=>hash('sha256',canonical($before))]);
    check(mkdir($root.'/asset-01',0700),'once_item');save($root.'/asset-01/live-manifest.json',$m);
    $result=\Mosa2\MarketCurrent\run($root,$password,$config,[['private_root'=>$root.'/asset-01']],$approvals);
    $report=['ok'=>false,'status'=>'OUTCOME_UNKNOWN','commit'=>$commit,'run'=>$run,'isin'=>$r['isin'],
        'asset'=>$r['display_name'],'source'=>$r['source_name'],'scope'=>$scope,'provider_requests'=>$result['provider_requests']??null,
        'batch_status'=>$result['overall_status']??null,'current'=>$result['current']['decisions']??null];
    save($root.'/pipeline.json',$report+['items'=>$result['item_results']??[],
        'current_commit'=>$result['current']['committed']??null,'current_readback'=>$result['current']['readback']??null]);
    check(($result['ok']??false)===true&&($result['overall_status']??null)==='COMPLETE','once_pipeline_incomplete');
    same($result['provider_requests'],1,'once_provider_budget');same($result['completed_count'],1,'once_batch_scope');
    check(($result['current']['committed']??false)===true&&($result['current']['readback']??null)==='PASS','once_current_readback');
    // A new connection independently reads the final stored provenance and the actual publication boundary.
    $p=connection($password);unset($password,$in);$p->exec('SET TRANSACTION READ ONLY');check($p->beginTransaction(),'once_readback');
    try{
        $after=\Mosa2\MarketLive\snapshot($p,$config['state_contract']);unchanged($before,$after,$scope);
        $inputs=\Mosa2\MarketCurrent\inputs($p,$approvals,stamp());
        same(array_column(\Mosa2\MarketCurrent\plans($config,$inputs),'decision'),['UNCHANGED'],'once_current_replay');
        $published=\Mosa2\CurrentRead\published($p,stamp(),1800);
        $display=array_values(array_filter($published,static fn($v)=>$v['route']['asset_id']===$scope['asset_id']));same(count($display),1,'once_display');
        $report+=['observation_id'=>$result['item_results'][0]['observation_id'],'observation_writer'=>$result['item_results'][0]['writer'],
            'current_observation_id'=>$inputs[0]['current']['observation_id'],'display'=>$display[0]['item'],
            'readback'=>'PASS','other_business_data'=>'UNCHANGED','route_enabled'=>$route[0]['enabled']];
    }finally{if($p->inTransaction())$p->rollBack();$p=null;}
    $report['ok']=true;$report['status']='COMPLETE';return $report;
}
function main(): void {
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{$wire=stream_get_contents(STDIN,8193);check(strlen($wire)<=8192,'once_input_limit');
        $in=json_decode($wire,true,32,JSON_THROW_ON_ERROR);$report=run($in,dirname(__DIR__));}
    catch(Throwable $e){$report=['ok'=>false,'status'=>'OUTCOME_UNKNOWN','failure_type'=>$e instanceof \PDOException?'DATABASE_OPERATION_FAILED':'CONTRACT_CHECK_FAILED'];
        if(preg_match('/^(once_[a-z_]+|pinned_php_required|pinned_python_required)$/D',$e->getMessage()))$report['failure_code']=$e->getMessage();}
    unset($wire,$in);echo json_encode($report,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__)main();
