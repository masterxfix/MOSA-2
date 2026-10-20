<?php
declare(strict_types=1);
namespace Mosa2\MarketCurrent;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,connection};
require_once __DIR__.'/../market_collector/live_batch.php';

const CONTRACT=['schema_version'=>4,'allow_current'=>true];

/** Compare physical route IDs returned by the existing onboarding planner. */
function approvalScope(array $state,array $prepared,array $approvals): void {
    $selected=[];
    foreach($prepared as $entry){$plan=\Mosa2\MarketLive\completePlan($state,$entry['manifest']);$selected[]=$plan['route']['route_id'];}
    $approved=array_column($approvals,'route_id');sort($selected);sort($approved);same($selected,$approved,'current_batch_approval_scope');
}

/** At most two candidates per explicitly approved physical route; no provider I/O. */
function inputs(PDO $p,array $approvals,string $now): array {
    check(count($approvals)>0&&count($approvals)<=10,'current_scope');$items=[];$seen=[];$assets=[];
    foreach($approvals as $approval){
        $id=$approval['route_id'];check(is_string($id)&&preg_match('/^[1-9][0-9]*$/D',$id)===1&&!isset($seen[$id]),'current_route_scope');$seen[$id]=true;
        $q=$p->prepare('SELECT * FROM m2_asset_source_routes WHERE id=?');$q->execute([$id]);$route=$q->fetch();check($route!==false,'current_route_missing');$route=\Mosa2\MarketLive\strings($route);
        check(!isset($assets[$route['asset_id']]),'current_duplicate_asset');$assets[$route['asset_id']]=true;
        $q=$p->prepare("SELECT a.entity_id FROM m2_assets a JOIN m2_entities e ON e.id=a.entity_id JOIN m2_sources s ON s.id=? WHERE a.entity_id=? AND e.status='active' AND s.enabled=1 AND s.source_type='market_data'");$q->execute([$route['source_id'],$route['asset_id']]);check($q->fetchColumn()!==false,'current_reference_status');
        $q=$p->prepare('SELECT *,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE asset_id=? AND source_id=? AND route_id=? AND observation_format_version=2 ORDER BY market_at DESC,observed_at DESC,id DESC LIMIT 2');
        $q->execute([$route['asset_id'],$route['source_id'],$id]);$facts=array_map('Mosa2\\MarketLive\\strings',$q->fetchAll());
        $q=$p->prepare('SELECT *,HEX(observation_dedupe_key) AS observation_dedupe_key FROM m2_market_current WHERE asset_id=?');$q->execute([$route['asset_id']]);$current=$q->fetch();$old=null;
        if($current!==false){$current=\Mosa2\MarketLive\strings($current);$q=$p->prepare('SELECT *,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE id=?');$q->execute([$current['observation_id']]);$old=$q->fetch();check($old!==false,'current_origin_missing');$old=\Mosa2\MarketLive\strings($old);}
        $items[]=['route'=>$route,'approval'=>$approval,'facts'=>$facts,'current'=>$current===false?null:$current,'current_fact'=>$old,'now'=>$now];
    }return $items;
}
function plans(array $config,array $items): array {
    $proc=proc_open([$config['python'],$config['project'].'/scripts/market_current/planner.py'],[0=>['pipe','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes,$config['project'],['PATH'=>$config['runtime_path'],'PYTHONDONTWRITEBYTECODE'=>'1']);check(is_resource($proc),'current_planner_process');
    try{$wire=json_encode(['items'=>$items],JSON_THROW_ON_ERROR);check(fwrite($pipes[0],$wire)===strlen($wire),'current_planner_input');fclose($pipes[0]);$out=stream_get_contents($pipes[1]);$err=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);same(proc_close($proc),0,'current_planner_exit');$proc=null;same($err,'','current_planner_stderr');}
    finally{if(is_resource($proc))proc_close($proc);}
    $reply=json_decode($out,true,512,JSON_THROW_ON_ERROR);check(($reply['ok']??false)===true,'current_plan_'.($reply['failure']??'invalid'));same(count($reply['plans']),count($items),'current_plan_count');return $reply['plans'];
}
/** Current-only atomic transaction; all other business tables must remain identical. */
function refresh(string $password,array $config,array $approvals): array {
    $p=connection($password);$locked=false;$committed=false;$before=null;$after=null;
    try{
        $q=$p->query("SELECT GET_LOCK('m2-current-refresh',0)");$locked=(int)$q->fetchColumn()===1;check($locked,'current_lock_busy');$p->beginTransaction();
        $before=\Mosa2\MarketLive\snapshot($p,CONTRACT);
        $now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');$items=inputs($p,$approvals,$now);$plans=plans($config,$items);$expected=$before['m2_market_current'];
        foreach($plans as $i=>$plan){
            if(in_array($plan['decision'],['INSERT','UPDATE'],true)){
                $values=$plan['values'];$fields=array_keys($values);$expressions=array_map(static fn($f)=>$f==='observation_dedupe_key'?'UNHEX(?)':'?',$fields);
                if($plan['decision']==='INSERT')$sql='INSERT INTO m2_market_current ('.implode(',',array_map('Mosa2\\Phase2\\qi',$fields)).') VALUES ('.implode(',',$expressions).')';
                else {$sql='UPDATE m2_market_current SET '.implode(',',array_map(static fn($f,$e)=>qi($f).'='.$e,$fields,$expressions)).' WHERE asset_id=?';$values[]=$plan['values']['asset_id'];}
                $q=$p->prepare($sql);$q->execute(array_values($values));same($q->rowCount(),1,'current_write_count');
                $expected=array_values(array_filter($expected,static fn($r)=>$r['asset_id']!==$plan['values']['asset_id']));$expected[]=$plan['values'];
            }else check(in_array($plan['decision'],['MISSING','UNCHANGED','UNCHANGED_OLDER'],true),'current_decision');
        }
        $after=\Mosa2\MarketLive\snapshot($p,CONTRACT);$actual=$after['m2_market_current'];
        $sort=static function(&$rows){usort($rows,static fn($a,$b)=>strlen($a['asset_id'])<=>strlen($b['asset_id'])?:strcmp($a['asset_id'],$b['asset_id']));foreach($rows as &$r)ksort($r);};$sort($expected);$sort($actual);same($actual,$expected,'current_exact_readback');
        $other=$after;$other['m2_market_current']=$before['m2_market_current'];same($other,$before,'current_unplanned_delta');same($p->commit(),true,'current_commit');$committed=true;
    }finally{if($p->inTransaction())$p->rollBack();if($locked)$p->query("SELECT RELEASE_LOCK('m2-current-refresh')");$p=null;}
    $read=connection($password);unset($password);$read->exec('SET TRANSACTION READ ONLY');$read->beginTransaction();
    try{same(\Mosa2\MarketLive\snapshot($read,CONTRACT),$after,'current_independent_readback');}finally{$read->rollBack();$read=null;}
    return ['committed'=>$committed,'readback'=>'PASS','decisions'=>array_column($plans,'decision'),'private_evidence'=>['before'=>$before,'after'=>$after,'inputs'=>$items,'plans'=>$plans]];
}
/** Existing sequential collector first; Current projection only after COMPLETE. */
function run(string $root,string $password,array $config,array $entries,array $approvals): array {
    $config['state_contract']=CONTRACT;$config['allow_duplicate']=true;
    $pre=null;$attempts=0;
    try{
        $prepared=\Mosa2\MarketBatch\prepare($root,$config['public_root'],$entries);
        $attempts++;$pre=connection($password);$pre->exec('SET TRANSACTION READ ONLY');$pre->beginTransaction();
        $state=\Mosa2\MarketLive\snapshot($pre,CONTRACT);approvalScope($state,$prepared,$approvals);
        plans($config,inputs($pre,$approvals,(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u')));
    }catch(Throwable $error){return ['overall_status'=>'FAILED_BEFORE_FIRST_ITEM','provider_requests'=>0,'database_connections'=>$attempts,'failure'=>'current_preflight','ok'=>false];}
    finally{if($pre!==null&&$pre->inTransaction())$pre->rollBack();$pre=null;}
    $result=\Mosa2\MarketBatch\run($root,$password,$config,$entries);
    $result['database_connections']=($result['database_connections']??0)+1;
    if(($result['overall_status']??null)==='COMPLETE'){
        try{$result['current']=refresh($password,$config,$approvals);$result['database_connections']+=2;$result['ok']=true;}
        catch(Throwable $e){$result['overall_status']='CURRENT_FAILED';$result['ok']=false;$result['database_connections']=null;$result['current_failure']=$e->getMessage();}
    }unset($password);return $result;
}
