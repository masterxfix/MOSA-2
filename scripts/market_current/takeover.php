<?php
declare(strict_types=1);
namespace Mosa2\CurrentTakeover;
use PDO;
use function Mosa2\Phase2\{check,same,connection};
require_once __DIR__.'/preview_read.php';

function fresh(PDO $p,string $now): array {
    $snapshot=\Mosa2\CurrentPreview\gather($p,$now,true);$items=[];
    foreach($snapshot['items'] as $entry){
        check(!isset($entry['blocked_reason']),'takeover_scope_read');
        $data=\Mosa2\CurrentPreview\qualify($entry);
        $data['qualified_scope']=array_intersect_key($entry,array_flip(['isin','name','scope_rows']));$items[]=$data;
    }return $items;
}
function atomicContract(PDO $p): void {
    $engines=$p->query('SELECT DISTINCT ENGINE FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE()')->fetchAll(PDO::FETCH_COLUMN);
    same($engines,['InnoDB'],'atomic_engines');
    same((string)$p->query('SELECT COUNT(*) FROM information_schema.triggers WHERE TRIGGER_SCHEMA=DATABASE()')->fetchColumn(),'0','no_trigger_side_effects');
}
function lockQueryReadOnlyProof(PDO $p): string {
    check($p->inTransaction(),'lock_proof_active');
    same((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn(),'1','lock_proof_readonly');
    try{
        $p->prepare(\Mosa2\ObservationRead\scopeSql().' FOR UPDATE');
        $proof='LOCK_QUERY_NATIVE_PREPARE_CONFIRMED';
    }catch(\PDOException $error){
        // MySQL 1792/25006 is the expected READ ONLY barrier for a locking read.
        // Never execute it, switch to READ WRITE, or accept syntax/permission errors.
        check(($error->errorInfo[0]??null)==='25006'&&(int)($error->errorInfo[1]??0)===1792,'lock_query_unexpected_error');
        $proof='READONLY_LOCK_QUERY_REJECTION_CONFIRMED';
    }
    check($p->inTransaction(),'lock_proof_still_active');
    same((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn(),'1','lock_proof_still_readonly');
    return $proof;
}
/** Existing writer account; only READ ONLY metadata/state proof, never a write probe. */
function readiness(string $password,int $port): array {
    $p=null;$stage='EXISTING_WRITER_AUTHENTICATION_OR_IDENTITY_FAILED';
    try{
        $p=connection($password,'127.0.0.1',$port);unset($password);
        $stage='EXISTING_WRITER_READONLY_STATE_FAILED';
        $p->exec('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
        $p->exec('SET SESSION TRANSACTION READ ONLY');check($p->beginTransaction()&&$p->inTransaction(),'readiness_transaction_start');
        same((string)$p->query('SELECT @@session.transaction_read_only')->fetchColumn(),'1','readiness_read_only');
        $stage='EXISTING_WRITER_RIGHTS_FAILED';
        $grants=$p->query('SHOW GRANTS')->fetchAll(PDO::FETCH_COLUMN);sort($grants);
        $expected=['GRANT USAGE ON *.* TO `h29077_mosa2_test`@`localhost`','GRANT ALL PRIVILEGES ON `h29077\\_mosa2\\_test`.* TO `h29077_mosa2_test`@`localhost`'];sort($expected);
        same($grants,$expected,'writer_existing_grants');
        $stage='EXISTING_WRITER_ATOMIC_ENGINE_OR_TRIGGER_FAILED';
        atomicContract($p);
        $stage='EXISTING_WRITER_LOCK_QUERY_PREPARE_FAILED';
        // Native server-side syntax/privilege preparation only; never execute a locking read here.
        $lockProof=lockQueryReadOnlyProof($p);
        $stage='EXISTING_WRITER_STATE_CONTRACT_FAILED';
        \Mosa2\MarketLive\snapshot($p,\Mosa2\MarketCurrent\CONTRACT);
        check($p->inTransaction(),'readiness_active');
        return ['status'=>'EXISTING_WRITER_RIGHTS_AND_ATOMIC_RUNTIME_CONFIRMED','lock_query_readonly_proof'=>$lockProof,'business_writes'=>0];
    }catch(\Throwable){return ['status'=>$stage,'business_writes'=>0];}
    finally{if($p!==null&&$p->inTransaction())$p->rollBack();$p=null;}
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    $outcome=new \Mosa2\MarketCurrent\Outcome(static function($event){echo json_encode($event,JSON_THROW_ON_ERROR)."\n";flush();});
    try{
        $outcome->step('PREFLIGHT');
        $in=json_decode(stream_get_contents(STDIN),true,512,JSON_THROW_ON_ERROR);
        if(($in['operation']??null)==='readiness'){
            $reply=readiness($in['password'],(int)$in['port']);
        }else{
            // No default execution mode: all execution authority must be explicit.
            same($in['operation']??null,'apply','takeover_operation');
            check(($in['attempt']??null)==='1','takeover_first_attempt');
            $config=$in['config'];$takeover=$in['takeover'];
            $items=[];foreach($takeover['plan']['items'] as $item){
                $data=$item['reference']['input'];$data['now']=$takeover['plan']['as_of'];
                $data['qualified_scope']=array_intersect_key($item['reference'],array_flip(['isin','name','scope_rows']));$items[]=$data;
            }
            \Mosa2\MarketCurrent\plans($config,$items,$takeover);
            same(readiness($in['password'],(int)$config['db_port'])['status'],
                'EXISTING_WRITER_RIGHTS_AND_ATOMIC_RUNTIME_CONFIRMED','takeover_runtime');
            $approvals=[];
            foreach($takeover['plan']['items'] as $item)$approvals[]=['route_id'=>$item['reference']['input']['route']['id'],
                'route_sha256'=>$item['route_sha256'],'approved_at'=>$takeover['plan']['as_of'],
                'allow_disabled_projection'=>$item['disabled_projection_required']===true];
            $outcome->budget();
            $result=\Mosa2\MarketCurrent\refresh($in['password'],$config,$approvals,$takeover,$outcome);
            $outcome->budget();$outcome->step('COMPLETE');
            $reply=$outcome->report(true);
        }
        echo json_encode(['kind'=>'final','ok'=>true]+$reply,JSON_THROW_ON_ERROR)."\n";
    }catch(\Throwable $error){
        if($outcome->cause==='NONE')$outcome->cause=$error->getMessage()==='current_planner_timeout'?'PLANNER_TIMEOUT':
            ($outcome->commit==='CONFIRMED'?'POST_COMMIT_ERROR':'PREFLIGHT_OR_TRANSACTION_ERROR');
        echo json_encode(['kind'=>'final','ok'=>false]+$outcome->report(),JSON_THROW_ON_ERROR)."\n";
    }
}
