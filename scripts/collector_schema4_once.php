<?php
declare(strict_types=1);
namespace Mosa2\Schema4Once;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,connection};
require_once __DIR__.'/market_current/refresh.php';
require_once __DIR__.'/market_collector/actions_acceptance.php';
require_once __DIR__.'/market_collector/tradegate_manifest.php';
require_once dirname(__DIR__).'/api/current_read.php';
require_once __DIR__.'/collector_release/runtime.php';

const ROOT='/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector';
const WEB='/var/www/vhosts/web213.server10.configcenter.info/mosa2-test.scharwerk.de';
const FIVE_NAMES=['BYD','DroneShield','Ubtech Robotics','PNE AG','Carl Zeiss Meditec'];
const FIVE_AUTHORIZATION='MOSA2-SCHEMA4-FIVE-20261031:';
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
/** One central explicit name scope; identities come only from validated published DB relationships. */
function selected(array $published,string $mode): array {
    if($mode==='one')return [choose($published)];
    same($mode,'five','once_scope');
    $out=[];$seen=[];
    foreach(FIVE_NAMES as $name){
        $matches=array_values(array_filter($published,static fn($e)=>$e['route']['display_name']===$name));
        same(count($matches),1,'once_published_scope');$entry=$matches[0];$r=$entry['route'];
        same($r['asset_class'],'equity','once_equity');same($r['quote_unit_key'],'EUR','once_eur');
        same($r['quote_unit_version'],'1','once_eur');check(!isset($seen[$r['isin']]),'once_duplicate_isin');
        $seen[$r['isin']]=true;$out[]=$entry;
    }
    return $out;
}
/** The same byte contract as MarketCurrent.planner.route_hash; never enable the route. */
function approval(array $route,string $now): array {
    return ['route_id'=>$route['id'],'route_sha256'=>hash('sha256',canonical($route)),
        'approved_at'=>$now,'allow_disabled_projection'=>true];
}
/** The one-shot may add one provider and one inactive route for the existing asset. */
function prepareTradegate(PDO $p,array $before,array $selection,string $now): array {
    same(\Mosa2\MarketLive\snapshot($p,['schema_version'=>4,'allow_current'=>true]),$before,'once_catalog_drift');
    $sourcePlan=\Mosa2\TradegateQuote\sourcePlan($before['m2_sources'],$now);
    $working=$before;$inserted=['m2_sources'=>[],'m2_asset_source_routes'=>[]];
    if($sourcePlan['decision']==='INSERT'){
        $values=$sourcePlan['values'];$fields=array_keys($values);
        $q=$p->prepare('INSERT INTO m2_sources ('.implode(',',array_map('Mosa2\\Phase2\\qi',$fields)).') VALUES ('.implode(',',array_fill(0,count($fields),'?')).')');
        $q->execute(array_values($values));same($q->rowCount(),1,'once_source_insert');$id=$p->lastInsertId();
        $q=$p->prepare('SELECT * FROM m2_sources WHERE id=?');$q->execute([$id]);$row=$q->fetch(PDO::FETCH_ASSOC);check($row!==false,'once_source_readback');
        $source=\Mosa2\MarketLive\strings($row);same($source,['id'=>$id]+\Mosa2\MarketLive\strings($values),'once_source_values');
        $working['m2_sources'][]=$source;$inserted['m2_sources'][]=$source;
    }else{same($sourcePlan['decision'],'EXISTING_MATCH','once_source_plan');$source=$sourcePlan['row'];}
    $manifest=\Mosa2\TradegateQuote\manifest($working,$selection);
    $plan=\Mosa2\MarketLive\completePlan($working,$manifest);
    same($plan['asset']['decision'],'EXISTING_MATCH','once_existing_asset');
    $route=\Mosa2\MarketLive\strings(\Mosa2\MarketIdentity\applyMarketRoutePlan(
        new \Mosa2\MarketIdentity\PdoStore($p),$plan['route'],$plan['asset']['asset_id'],$now));
    if($plan['route']['decision']==='CREATE_REVISION')$inserted['m2_asset_source_routes'][]=$route;
    $after=\Mosa2\MarketLive\snapshot($p,['schema_version'=>4,'allow_current'=>true]);
    $deltas=array_map('count',$inserted);
    \Mosa2\MarketLive\compareDelta($before,$after,['deltas'=>$deltas],$inserted);
    $manifest['policy']='USE_EXISTING_ROUTE';\Mosa2\MarketLive\completePlan($after,$manifest);
    return ['state'=>$after,'manifest'=>$manifest,'route'=>$route,'source'=>$source,'deltas'=>$deltas];
}
/** Full before/after proof is explicit to this one-asset acceptance, not a new runtime path. */
function unchanged(array $before,array $after,array $scope): void {
    $scopes=isset($scope['asset_id'])?[$scope]:$scope;
    $assetIds=array_column($scopes,'asset_id');
    foreach($before as $table=>$rows){
        if($table==='m2_market_observations'){
            $old=array_column($rows,'id');$added=[];$kept=[];
            foreach($after[$table] as $r){if(in_array($r['id'],$old,true))$kept[]=$r;else $added[]=$r;}
            same($kept,$rows,'once_old_observations_changed');check(count($added)<=count($scopes),'once_observation_budget');
            foreach($added as $r){$matching=array_values(array_filter($scopes,static fn($s)=>$s['asset_id']===$r['asset_id']));same(count($matching),1,'once_observation_scope');foreach(['asset_id','source_id','route_id'] as $k)same($r[$k],$matching[0][$k],'once_observation_scope');}
        }elseif($table==='m2_market_current'){
            $other=static fn($r)=>!in_array($r['asset_id'],$assetIds,true);
            same(array_values(array_filter($after[$table],$other)),array_values(array_filter($rows,$other)),'once_other_current_changed');
            same(count($after[$table]),count($rows),'once_current_scope');
        }else same($after[$table],$rows,'once_unplanned_business_write');
    }
}
function run(array $in,string $project): array {
    $commit=$in['commit']??'';$run=$in['run']??'';
    check(is_string($commit)&&preg_match('/^[a-f0-9]{40}$/D',$commit)===1,'once_commit');
    same($project,ROOT.'/releases/'.$commit,'once_release');same(realpath($project),$project,'once_release_path');
    $mode=$in['scope']??'one';check(in_array($mode,['one','five'],true),'once_scope');
    same($in['authorization']??null,($mode==='five'?FIVE_AUTHORIZATION:AUTHORIZATION).$commit,'once_authorization');
    check(is_string($run)&&preg_match('/^schema4-[a-f0-9]{40}-[1-9][0-9]{0,19}$/D',$run)===1,'once_run');
    check(str_starts_with($run,'schema4-'.$commit.'-'),'once_run_binding');
    $root=ROOT.'/runs/'.$run;same(realpath($root),$root,'once_run_path');
    check(!is_link($root)&&fileowner($root)===10317&&filegroup($root)===1003&&(fileperms($root)&0777)===0700,'once_run_metadata');
    $password=$in['password'];check(is_string($password)&&$password!=='','once_secret');
    $config=\Mosa2\CollectorRelease\configuration($project,4,'3.11.18');
    $config['state_contract']=['schema_version'=>4,'allow_current'=>true];$config['public_root']=WEB;
    $p=connection($password);$p->exec('SET SESSION max_execution_time=10000');
    $p->exec('SET TRANSACTION READ ONLY');check($p->beginTransaction(),'once_preflight');
    try{
        $before=\Mosa2\MarketLive\snapshot($p,$config['state_contract']);
        foreach($before as $rows)check(count($rows)<=10000,'once_test_state_bound');
        $selected=selected(\Mosa2\CurrentRead\published($p,stamp(),1800),$mode);$old=[];
        foreach($selected as $entry){$r=$entry['route'];$match=array_values(array_filter($before['m2_asset_source_routes'],static fn($v)=>$v['id']===$r['route_id']));same(count($match),1,'once_route');$old[]=$match[0];}
    }finally{if($p->inTransaction())$p->rollBack();$p=null;}
    // Catalog registration does not enable unattended execution. The existing
    // scope-bound reservation permits at most one acquisition per selected identity.
    $p=connection($password);check($p->beginTransaction(),'once_catalog_transaction');
    try{
        $catalogs=[];$working=$before;$deltas=['m2_sources'=>0,'m2_asset_source_routes'=>0];
        foreach($selected as $entry){
            $r=$entry['route'];$catalog=prepareTradegate($p,$working,['isin'=>$r['isin'],'name'=>$r['display_name']],stamp());
            $working=$catalog['state'];$catalogs[]=$catalog;
            foreach($deltas as $key=>$value)$deltas[$key]+=$catalog['deltas'][$key];
        }
        same($p->commit(),true,'once_catalog_commit');
    }finally{if($p->inTransaction())$p->rollBack();$p=null;}
    $before=$working;$scopes=[];$approvals=[];$entries=[];
    foreach($catalogs as $i=>$catalog){
        $route=$catalog['route'];$scopes[]=['asset_id'=>$route['asset_id'],'source_id'=>$route['source_id'],'route_id'=>$route['id']];
        $approvals[]=approval($route,stamp())+['run_id'=>$run,'commit'=>$commit,
            'allow_route_transition'=>true,'previous_route_sha256'=>hash('sha256',canonical($old[$i]))];
        $folder=$root.'/asset-'.sprintf('%02d',$i+1);check(mkdir($folder,0700),'once_item');
        save($folder.'/live-manifest.json',$catalog['manifest']);$entries[]=['private_root'=>$folder];
    }
    save($root.'/preflight.json',['commit'=>$commit,'run'=>$run,'scopes'=>$scopes,
        'approvals'=>$approvals,'catalog_deltas'=>$deltas,'before_sha256'=>hash('sha256',canonical($before))]);
    $result=\Mosa2\MarketCurrent\run($root,$password,$config,$entries,$approvals);
    $report=['ok'=>false,'status'=>'OUTCOME_UNKNOWN','commit'=>$commit,'run'=>$run,'request_scope'=>$mode,
        'catalog_deltas'=>$deltas,'provider_requests'=>$result['provider_requests']??null,
        'batch_status'=>$result['overall_status']??null,'current'=>$result['current']['decisions']??null];
    save($root.'/pipeline.json',$report+['items'=>$result['item_results']??[],
        'current_commit'=>$result['current']['committed']??null,'current_readback'=>$result['current']['readback']??null]);
    check(($result['ok']??false)===true&&($result['overall_status']??null)==='COMPLETE','once_pipeline_incomplete');
    same($result['provider_requests'],count($selected),'once_provider_budget');same($result['completed_count'],count($selected),'once_batch_scope');
    check(($result['current']['committed']??false)===true&&($result['current']['readback']??null)==='PASS','once_current_readback');
    // A new connection independently reads the final stored provenance and the actual publication boundary.
    $p=connection($password);unset($password,$in);$p->exec('SET TRANSACTION READ ONLY');check($p->beginTransaction(),'once_readback');
    try{
        $after=\Mosa2\MarketLive\snapshot($p,$config['state_contract']);unchanged($before,$after,$scopes);
        $inputs=\Mosa2\MarketCurrent\inputs($p,$approvals,stamp());
        same(array_column(\Mosa2\MarketCurrent\plans($config,$inputs),'decision'),array_fill(0,count($selected),'UNCHANGED'),'once_current_replay');
        $published=\Mosa2\CurrentRead\published($p,stamp(),1800);$items=[];
        foreach($scopes as $i=>$scope){
            foreach(['asset_id','source_id','route_id'] as $key)same($inputs[$i]['current'][$key],$scope[$key],'once_current_source');
            $display=array_values(array_filter($published,static fn($v)=>$v['route']['asset_id']===$scope['asset_id']));same(count($display),1,'once_display');
            $items[]=['asset'=>$selected[$i]['route']['display_name'],'isin'=>$selected[$i]['route']['isin'],
                'source'=>$catalogs[$i]['source']['display_name'],'quote_kind'=>'mid','scope'=>$scope,
                'observation_id'=>$result['item_results'][$i]['observation_id'],'observation_writer'=>$result['item_results'][$i]['writer'],
                'current_observation_id'=>$inputs[$i]['current']['observation_id'],'current'=>$result['current']['decisions'][$i],
                'display'=>$display[0]['item'],'readback'=>'PASS','route_enabled'=>$catalogs[$i]['route']['enabled']];
        }
        $report+=['items'=>$items,'readback'=>'PASS','other_business_data'=>'UNCHANGED'];
        if($mode==='one')$report+=$items[0];
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
