<?php
declare(strict_types=1);
namespace Mosa2\MarketCurrent;
use PDO;
use Throwable;
use function Mosa2\Phase2\{check,same,qi,connection};
require_once __DIR__.'/../market_collector/live_batch.php';
require_once __DIR__.'/outcome.php';
require_once __DIR__.'/bounded_process.php';

const CONTRACT=['schema_version'=>4,'allow_current'=>true];

/** Compare physical route IDs returned by the existing onboarding planner. */
function approvalScope(array $state,array $prepared,array $approvals): void {
    $selected=[];
    foreach($prepared as $entry){$plan=\Mosa2\MarketLive\completePlan($state,$entry['manifest']);$selected[]=$plan['route']['route_id'];}
    $approved=array_column($approvals,'route_id');sort($selected);sort($approved);same($selected,$approved,'current_batch_approval_scope');
}

/** At most two candidates per explicitly approved physical route; no provider I/O. */
function inputs(PDO $p,array $approvals,string $now,bool $lock=false): array {
    $suffix=$lock?' FOR UPDATE':'';
    check(count($approvals)>0&&count($approvals)<=10,'current_scope');$items=[];$seen=[];$assets=[];
    foreach($approvals as $approval){
        $id=$approval['route_id'];check(is_string($id)&&preg_match('/^[1-9][0-9]*$/D',$id)===1&&!isset($seen[$id]),'current_route_scope');$seen[$id]=true;
        $q=$p->prepare('SELECT * FROM m2_asset_source_routes WHERE id=?'.$suffix);$q->execute([$id]);$route=$q->fetch();check($route!==false,'current_route_missing');$route=\Mosa2\MarketLive\strings($route);
        check(!isset($assets[$route['asset_id']]),'current_duplicate_asset');$assets[$route['asset_id']]=true;
        $q=$p->prepare("SELECT a.entity_id FROM m2_assets a JOIN m2_entities e ON e.id=a.entity_id JOIN m2_sources s ON s.id=? WHERE a.entity_id=? AND e.status='active' AND s.enabled=1 AND s.source_type='market_data'".$suffix);$q->execute([$route['source_id'],$route['asset_id']]);check($q->fetchColumn()!==false,'current_reference_status');
        $q=$p->prepare('SELECT *,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE asset_id=? AND source_id=? AND route_id=? AND observation_format_version=2 ORDER BY market_at DESC,observed_at DESC,id DESC LIMIT 2'.$suffix);
        $q->execute([$route['asset_id'],$route['source_id'],$id]);$facts=array_map('Mosa2\\MarketLive\\strings',$q->fetchAll());
        $q=$p->prepare('SELECT *,HEX(observation_dedupe_key) AS observation_dedupe_key FROM m2_market_current WHERE asset_id=?'.$suffix);$q->execute([$route['asset_id']]);$current=$q->fetch();$old=null;
        if($current!==false){$current=\Mosa2\MarketLive\strings($current);$q=$p->prepare('SELECT *,HEX(dedupe_key) AS dedupe_key FROM m2_market_observations WHERE id=? AND asset_id=?'.$suffix);$q->execute([$current['observation_id'],$route['asset_id']]);$old=$q->fetch();check($old!==false,'current_origin_missing');$old=\Mosa2\MarketLive\strings($old);}
        $items[]=['route'=>$route,'approval'=>$approval,'facts'=>$facts,'current'=>$current===false?null:$current,'current_fact'=>$old,'now'=>$now];
    }return $items;
}
function plans(array $config,array $items,?array $takeover=null): array {
    $script=$takeover===null?'/scripts/market_current/planner.py':'/scripts/market_current/takeover.py';
    $out=boundedPlanner([$config['python'],$config['project'].$script],
        json_encode(['items'=>$items,'takeover'=>$takeover],JSON_THROW_ON_ERROR),$config,(float)($config['planner_seconds']??60));
    $reply=json_decode($out,true,512,JSON_THROW_ON_ERROR);check(($reply['ok']??false)===true,'current_plan_'.($reply['failure']??'invalid'));same(count($reply['plans']),count($items),'current_plan_count');return $reply['plans'];
}
/** Current-only atomic transaction; all other business tables must remain identical. */
function transaction(PDO $p,callable $readInputs,callable $makePlans,callable $capture,?Outcome $outcome=null): array {
    $outcome??=new Outcome();
    $locked=false;$committed=false;$before=null;$after=null;
    try{
        $q=$p->query("SELECT GET_LOCK('m2-current-refresh',0)");$locked=(int)$q->fetchColumn()===1;check($locked,'current_lock_busy');
        $outcome->budget(true);$outcome->step('TRANSACTION_BEGIN');
        $p->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');check($p->beginTransaction()&&$p->inTransaction(),'current_transaction_start');
        $outcome->transaction=true;$outcome->step('TRANSACTION_ACTIVE');
        $before=$capture($p);
        $now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');$items=$readInputs($p,$now);$plans=$makePlans($items);$expected=$before['m2_market_current'];
        foreach($plans as $i=>$plan){
            if(in_array($plan['decision'],['INSERT','UPDATE'],true)){
                $values=$plan['values'];$fields=array_keys($values);$expressions=array_map(static fn($f)=>$f==='observation_dedupe_key'?'UNHEX(?)':'?',$fields);
                if($plan['decision']==='INSERT')$sql='INSERT INTO m2_market_current ('.implode(',',array_map('Mosa2\\Phase2\\qi',$fields)).') VALUES ('.implode(',',$expressions).')';
                else {$sql='UPDATE m2_market_current SET '.implode(',',array_map(static fn($f,$e)=>qi($f).'='.$e,$fields,$expressions)).' WHERE asset_id=?';$values[]=$plan['values']['asset_id'];}
                $outcome->budget(true);$outcome->writeAttempted=true;
                $q=$p->prepare($sql);$q->execute(array_values($values));same($q->rowCount(),1,'current_write_count');
                $expected=array_values(array_filter($expected,static fn($r)=>$r['asset_id']!==$plan['values']['asset_id']));$expected[]=$plan['values'];
            }else check(in_array($plan['decision'],['MISSING','UNCHANGED','UNCHANGED_OLDER'],true),'current_decision');
        }
        $after=$capture($p);$actual=$after['m2_market_current'];
        $sort=static function(&$rows){usort($rows,static fn($a,$b)=>strlen($a['asset_id'])<=>strlen($b['asset_id'])?:strcmp($a['asset_id'],$b['asset_id']));foreach($rows as &$r)ksort($r);};$sort($expected);$sort($actual);same($actual,$expected,'current_exact_readback');
        $other=$after;$other['m2_market_current']=$before['m2_market_current'];same($other,$before,'current_unplanned_delta');
        $outcome->budget(true);$outcome->commit='UNKNOWN';$outcome->step('COMMIT_ATTEMPT');
        same($p->commit(),true,'current_commit');$committed=true;
        $outcome->commit='CONFIRMED';$outcome->step('COMMIT_CONFIRMED');
    }catch(Throwable $error){
        if($outcome->cause==='NONE')$outcome->cause=$error->getMessage()==='current_planner_timeout'?'PLANNER_TIMEOUT':'TRANSACTION_ERROR';
        throw $error;
    }finally{
        try{
            if($p->inTransaction()){
                $outcome->rollback='UNKNOWN';
                if($p->rollBack()&&!$p->inTransaction())$outcome->rollback='CONFIRMED';
                else throw new \RuntimeException('current_rollback_unconfirmed');
                $outcome->step('ROLLBACK');
            }
        }finally{
            try{if($locked)same((string)$p->query("SELECT RELEASE_LOCK('m2-current-refresh')")->fetchColumn(),'1','current_unlock');}
            finally{$p=null;}
        }
    }
    return ['committed'=>$committed,'readback'=>'PENDING','decisions'=>array_column($plans,'decision'),'private_evidence'=>['before'=>$before,'after'=>$after,'inputs'=>$items,'plans'=>$plans]];
}
function verifyReadback(array $result,array $actual,?array $replay=null,?Outcome $outcome=null): array {
    check(($result['committed']??false)===true,'current_commit_not_confirmed');
    same($actual,$result['private_evidence']['after'],'current_independent_readback');
    if($outcome!==null){$outcome->readback=true;$outcome->step('READBACK_CONFIRMED');}
    if($replay!==null)same(array_column($replay,'decision'),array_fill(0,5,'UNCHANGED'),'current_replay');
    if($outcome!==null&&$replay!==null){$outcome->replay=true;$outcome->step('REPLAY_CONFIRMED');}
    $result['readback']='PASS';return $result;
}
function refresh(string $password,array $config,array $approvals,?array $takeover=null,?Outcome $outcome=null): array {
    $outcome??=new Outcome();
    $connect=static fn()=>connection($password,'127.0.0.1',(int)($config['db_port']??3307));
    $capture=static function(PDO $db)use($takeover){
        $state=\Mosa2\MarketLive\snapshot($db,CONTRACT);
        if($takeover!==null)\Mosa2\CurrentTakeover\atomicContract($db);
        return $state;
    };
    if($takeover!==null)require_once __DIR__.'/takeover.php';
    $readInputs=$takeover===null?static fn(PDO $db,string $now)=>inputs($db,$approvals,$now):
        static fn(PDO $db,string $now)=>\Mosa2\CurrentTakeover\fresh($db,$now);
    $writer=$connect();
    if($takeover!==null){
        $writer->exec('SET SESSION innodb_lock_wait_timeout=10');
        $writer->exec('SET SESSION max_execution_time=10000');
    }
    try{$result=transaction($writer,$readInputs,static fn($items)=>plans($config,$items,$takeover),$capture,$outcome);}
    finally{$writer=null;}
    $outcome->budget();$outcome->step('READBACK');
    $read=$connect();unset($password);
    $read->exec('SET SESSION max_execution_time=10000');
    $read->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $read->exec('SET SESSION TRANSACTION READ ONLY');check($read->beginTransaction()&&$read->inTransaction(),'readback_transaction_start');
    try{
        same((string)$read->query('SELECT @@session.transaction_read_only')->fetchColumn(),'1','readback_read_only');
        $actual=$capture($read);$replay=null;
        verifyReadback($result,$actual,null,$outcome);
        $outcome->budget();
        if($takeover!==null){
            $now=(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))->format('Y-m-d H:i:s.u');
            $outcome->step('REPLAY');$config['planner_seconds']=45;
            $replayItems=inputs($read,$approvals,$now);$replay=plans($config,$replayItems);
        }
        return verifyReadback($result,$actual,$replay,$outcome);
    }finally{
        try{if($read->inTransaction())check($read->rollBack()&&!$read->inTransaction(),'readback_rollback');}
        finally{$read=null;}
    }
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
        catch(Throwable $e){$result['overall_status']='CURRENT_FAILED';$result['ok']=false;$result['database_connections']=null;$result['current_failure']='CURRENT_REFRESH_FAILED';}
    }unset($password);return $result;
}
