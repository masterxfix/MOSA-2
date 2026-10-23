<?php
declare(strict_types=1);
namespace Mosa2\Scheduler;

use PDO;
use Throwable;
use RuntimeException;
use function Mosa2\Phase2\{check,same,connection};
require_once __DIR__.'/market_current/refresh.php';

/** Schema-4 job history is the durable stop latch; no lease expiry or auto-reset. */
interface RunStore {
    public function lock(): bool;
    public function unlock(): void;
    public function history(): array;
    public function claim(string $slot,int $requests,string $started): string;
    public function finish(string $id,array $summary,string $finished,bool $success): void;
}
function canonical(mixed $value): mixed {
    if(!is_array($value))return $value;
    if(!array_is_list($value))ksort($value,SORT_STRING);
    foreach($value as &$item)$item=canonical($item);
    return $value;
}
final class PdoRuns implements RunStore {
    private ?string $job=null;
    public function __construct(private PDO $db) {}
    public function lock(): bool {
        return (string)$this->db->query("SELECT GET_LOCK('m2-collector-scheduler',0)")->fetchColumn()==='1';
    }
    public function unlock(): void {
        same((string)$this->db->query("SELECT RELEASE_LOCK('m2-collector-scheduler')")->fetchColumn(),'1','scheduler_unlock');
    }
    private function job(): string {
        $q=$this->db->query("SELECT id,enabled,module_key,handler_key FROM m2_jobs WHERE job_key='market_collector_scheduler_v1' LIMIT 2");
        $rows=$q->fetchAll(PDO::FETCH_ASSOC);same(count($rows),1,'scheduler_job_required');
        $r=$rows[0];same((string)$r['enabled'],'1','scheduler_job_disabled');
        same($r['module_key'],'market_collector','scheduler_job_binding');
        same($r['handler_key'],'collector_scheduler_v1','scheduler_job_binding');
        return $this->job=(string)$r['id'];
    }
    public function history(): array {
        $id=$this->job();
        // All unresolved history, including older days, blocks. Never hide it behind a newer success.
        $q=$this->db->prepare("SELECT id FROM m2_job_runs WHERE job_id=? AND status<>'completed' LIMIT 1");
        $q->execute([$id]);check($q->fetchColumn()===false,'scheduler_unresolved');
        $columns='id,status,started_at,finished_at,attempt_no,summary_json';
        $day=(new \DateTimeImmutable('today',new \DateTimeZone('Europe/Berlin')))->setTimezone(new \DateTimeZone('UTC'));
        $q=$this->db->prepare('SELECT '.$columns.' FROM m2_job_runs WHERE job_id=? AND started_at>=? ORDER BY started_at DESC,id DESC LIMIT 2001');
        $q->execute([$id,stamp($day)]);$rows=$q->fetchAll(PDO::FETCH_ASSOC);check(count($rows)<=2000,'scheduler_history_bound');
        // Preserve the latest predecessor across midnight without enumerating old successful runs.
        $q=$this->db->prepare('SELECT '.$columns.' FROM m2_job_runs WHERE job_id=? ORDER BY started_at DESC,id DESC LIMIT 1');
        $q->execute([$id]);$latest=$q->fetch(PDO::FETCH_ASSOC);
        if($latest!==false&&!in_array($latest['id'],array_column($rows,'id'),true))$rows[]=$latest;
        return array_map(static function($r){
            return ['status'=>$r['status'],'started_at'=>str_replace(' ','T',$r['started_at']).'Z',
                'finished_at'=>$r['finished_at']===null?null:str_replace(' ','T',$r['finished_at']).'Z',
                'attempt_no'=>(int)$r['attempt_no'],'summary'=>json_decode($r['summary_json'],true,64,JSON_THROW_ON_ERROR)];
        },$rows);
    }
    public function claim(string $slot,int $requests,string $started): string {
        check(!$this->db->inTransaction(),'scheduler_transaction');
        check($this->db->beginTransaction(),'scheduler_transaction');
        try {
            // Re-read under the held named lock. No provider call occurs before commit confirmation.
            $this->history();
            $q=$this->db->prepare("INSERT INTO m2_job_runs (job_id,status,started_at,finished_at,attempt_no,summary_json,created_at) VALUES (?,'running',?,NULL,1,?,?)");
            $q->execute([$this->job,$started,json_encode(['contract'=>'mosa2-scheduler-v1','slot'=>$slot,'reserved_requests'=>$requests,'outcome'=>'OUTCOME_UNKNOWN'],JSON_THROW_ON_ERROR),$started]);
            same($q->rowCount(),1,'scheduler_claim');$id=$this->db->lastInsertId();
            same($this->db->commit(),true,'scheduler_claim_commit');
            // An independent receipt proves that the reservation survived commit.
            $q=$this->db->prepare("SELECT status,summary_json FROM m2_job_runs WHERE id=? AND job_id=?");
            $q->execute([$id,$this->job]);$row=$q->fetch(PDO::FETCH_ASSOC);
            check($row!==false&&$row['status']==='running','scheduler_claim_readback');
            $s=json_decode($row['summary_json'],true,16,JSON_THROW_ON_ERROR);
            same($s['slot'],$slot,'scheduler_claim_readback');same($s['reserved_requests'],$requests,'scheduler_claim_readback');
            return $id;
        }finally{if($this->db->inTransaction())$this->db->rollBack();}
    }
    public function finish(string $id,array $summary,string $finished,bool $success): void {
        $q=$this->db->prepare("UPDATE m2_job_runs SET status=?,finished_at=?,summary_json=? WHERE id=? AND job_id=? AND status='running' AND attempt_no=1");
        $q->execute([$success?'completed':'failed',$finished,json_encode($summary,JSON_THROW_ON_ERROR),$id,$this->job]);
        same($q->rowCount(),1,'scheduler_finish');
        $q=$this->db->prepare('SELECT status,summary_json FROM m2_job_runs WHERE id=? AND job_id=?');
        $q->execute([$id,$this->job]);$row=$q->fetch(PDO::FETCH_ASSOC);
        check($row!==false,'scheduler_finish_readback');same($row['status'],$success?'completed':'failed','scheduler_finish_readback');
        same(canonical(json_decode($row['summary_json'],true,64,JSON_THROW_ON_ERROR)),canonical($summary),'scheduler_finish_readback');
    }
}
function stamp(\DateTimeImmutable $now): string {return $now->setTimezone(new \DateTimeZone('UTC'))->format('Y-m-d H:i:s.u');}
function iso(string $stamp): string {return str_replace(' ','T',$stamp).'Z';}

/** One locked decision, one durable reservation, one call of the existing pipeline. */
function tick(RunStore $store,array $operation,array $budget,callable $qualify,callable $decide,callable $pipeline,callable $clock): array {
    $locked=false;$claimAttempted=false;
    try {
        if(($operation['execution_enabled']??false)!==true||($budget['execution_enabled']??false)!==true)
            return ['status'=>'SKIP','reason'=>'DISABLED'];
        $locked=$store->lock();if(!$locked)return ['status'=>'SKIP','reason'=>'BUSY'];
        $records=$store->history();
        $qualified=$qualify(); // Full shared registry/route/Current preflight, before reservation or directories.
        $now=$clock();$decision=$decide($records,$qualified,$now);
        if(($decision['decision']??null)!=='RUN_ELIGIBLE')
            return ['status'=>$decision['decision']??'BLOCKED','reason'=>$decision['reason']??'INVALID_EVIDENCE'];
        $slot=$decision['scheduled_at']??null;
        check(is_string($slot),'scheduler_slot');
        $start=$clock();$slotTime=new \DateTimeImmutable($slot);
        check($start>=$slotTime&&$start<$slotTime->modify('+1 minute'),'scheduler_missed_slot');
        $count=count($qualified['prepared']);check($count>=1&&$count<=10,'scheduler_scope');
        // No auto retry on a failed/ambiguous reservation commit, even if no provider was called.
        $claimAttempted=true;$id=$store->claim($slot,$count,stamp($start));
        $result=$pipeline($qualified,$decision['cycle_id']);
        $success=($result['ok']??false)===true&&($result['overall_status']??null)==='COMPLETE'
            &&($result['completed_count']??null)===$count&&($result['current']['committed']??false)===true
            &&($result['current']['readback']??null)==='PASS';
        $end=$clock();
        $envelope=['run_id'=>$decision['cycle_id'],'started_at'=>iso(stamp($start)),'completed_at'=>iso(stamp($end)),
            'receipt'=>['batch'=>array_intersect_key($result,array_flip(['overall_status','requested_count','started_count','completed_count',
                'provider_requests','insert_count','duplicate_unchanged_count','local_batch_ms','item_results']))]];
        $store->finish($id,['contract'=>'mosa2-scheduler-v1','slot'=>$slot,'reserved_requests'=>$count,
            'outcome'=>$success?'COMPLETE':'OUTCOME_UNKNOWN','envelope'=>$envelope],stamp($end),$success);
        return ['status'=>$success?'COMPLETE':'OUTCOME_UNKNOWN','reason'=>$success?'READBACK_PASS':'STOP_AND_REQUIRE_REVIEW'];
    }catch(Throwable){return ['status'=>$claimAttempted?'OUTCOME_UNKNOWN':'BLOCKED','reason'=>'STOP_AND_REQUIRE_REVIEW'];}
    finally{if($locked){try{$store->unlock();}catch(Throwable){/* Durable reservation remains authoritative; never retry. */}}}
}
function privateFile(string $file,string $publicRoot): string {
    check(is_file($file)&&!is_link($file)&&realpath($file)===$file,'scheduler_private_file');
    check(!\Mosa2\MarketBatch\inside($file,$publicRoot)&&(fileperms($file)&0077)===0,'scheduler_private_file');
    check(filesize($file)<=1048576,'scheduler_private_size');return file_get_contents($file);
}
/** One bounded JSON envelope over a pipe/socket; never a terminal, file or environment. */
function stdinPassword($input): string {
    check(is_resource($input)&&get_resource_type($input)==='stream','scheduler_secret');
    $stat=fstat($input);$kind=($stat['mode']??0)&0170000;
    check(in_array($kind,[0010000,0140000],true)&&!stream_isatty($input),'scheduler_secret');
    $meta=stream_get_meta_data($input);check(stream_set_blocking($input,false),'scheduler_secret');
    $wire='';$payload=null;$deadline=hrtime(true)/1e9+2;
    try{
        while(!feof($input)){
            $remaining=$deadline-hrtime(true)/1e9;check($remaining>0,'scheduler_secret');
            $read=[$input];$write=[];$except=[];
            $micros=max(1,(int)min(2000000,$remaining*1000000));
            $ready=stream_select($read,$write,$except,intdiv($micros,1000000),$micros%1000000);
            check($ready!==false,'scheduler_secret');if($ready===0)continue;
            $chunk=fread($input,4097-strlen($wire));check(is_string($chunk),'scheduler_secret');
            $wire.=$chunk;check(strlen($wire)<=4096,'scheduler_secret');
        }
        $payload=json_decode($wire,true,4,JSON_THROW_ON_ERROR);
        check(is_array($payload)&&array_keys($payload)===['password'],'scheduler_secret');
        $password=$payload['password'];
        check(is_string($password)&&strlen($password)>=1&&strlen($password)<=1024
            &&trim($password)!==''&&preg_match('/[\x00-\x1F\x7F]/',$password)===0,'scheduler_secret');
        return $password;
    }finally{
        unset($wire,$payload,$password);
        stream_set_blocking($input,(bool)($meta['blocked']??true));
    }
}

/** CLI only; no web include executes a scheduler, creates a directory or opens a DB. */
function main(array $args): array {
    check(PHP_SAPI==='cli','scheduler_cli');
    $project=dirname(__DIR__);
    $operation=json_decode(file_get_contents($project.'/config/collector-operation.json'),true,64,JSON_THROW_ON_ERROR);
    $budget=json_decode(file_get_contents($project.'/config/collector-provider-budget.json'),true,64,JSON_THROW_ON_ERROR);
    if(($operation['execution_enabled']??false)!==true||($budget['execution_enabled']??false)!==true)
        return ['status'=>'SKIP','reason'=>'DISABLED'];
    check(count($args)===2,'scheduler_cli');
    $password=stdinPassword(STDIN);
    require_once __DIR__.'/collector_release/runtime.php';
    $runtime=\Mosa2\CollectorRelease\configuration($project,4);
    // Explicitly approved existing private configuration; never search, provision or create paths here.
    $public='/var/www/vhosts/web213.server10.configcenter.info/mosa2-test.scharwerk.de';
    check(!\Mosa2\MarketBatch\inside(str_replace('\\','/',$project),$public),'scheduler_private_release');
    $spec=json_decode(privateFile($args[1],$public),true,64,JSON_THROW_ON_ERROR);
    $root=\Mosa2\MarketBatch\path($spec['private_root']);
    check(!\Mosa2\MarketBatch\inside($root,$public)&&(fileperms($root)&0077)===0,'scheduler_private_root');
    $runtime['public_root']=$public;$runtime['state_contract']=['schema_version'=>4,'allow_current'=>true];
    $clock=static fn()=>new \DateTimeImmutable('now',new \DateTimeZone('UTC'));
    $p=connection($password);$store=new PdoRuns($p);
    $qualify=static function()use($p,$operation,$spec,$runtime){
        $p->exec('SET TRANSACTION READ ONLY');check($p->beginTransaction(),'scheduler_preflight');
        try{
            $state=\Mosa2\MarketLive\snapshot($p,$runtime['state_contract']);
            $factory=static function($state,$asset)use($spec){
                $matches=array_values(array_filter($spec['manifests'],static fn($m)=>($m['identity']['normalized_value']??null)===$asset['isin']));
                same(count($matches),1,'scheduler_manifest_scope');return $matches[0];
            };
            $prepared=\Mosa2\MarketBatch\qualify($state,$operation['selection'],$factory);
            \Mosa2\MarketCurrent\approvalScope($state,$prepared,$spec['current_approvals']);
            \Mosa2\MarketCurrent\plans($runtime,\Mosa2\MarketCurrent\inputs($p,$spec['current_approvals'],stamp(new \DateTimeImmutable('now',new \DateTimeZone('UTC')))));
            $classes=[];foreach($prepared as $entry){$plan=\Mosa2\MarketLive\completePlan($state,$entry['manifest']);
                $asset=array_values(array_filter($state['m2_assets'],static fn($a)=>$a['entity_id']===$plan['asset']['asset_id']));
                $classes[]=$asset[0]['asset_class'];same($entry['manifest']['provider_key']??$entry['manifest']['route_evidence']['row']['provider_key'],$spec['provider'],'scheduler_provider_binding');}
            // cycle's qualification contract supports one class per run; a mixed scope is split explicitly, never silently.
            same(count(array_unique($classes)),1,'scheduler_class_scope');
            return ['prepared'=>$prepared,'qualification'=>['contract'=>'mosa2-operation-qualification-v1',
                'selection'=>$operation['selection'],'venue'=>$operation['venue'],'policy'=>'USE_EXISTING_ROUTE',
                'asset_class'=>$classes[0],'all_qualified'=>true]];
        }finally{if($p->inTransaction())$p->rollBack();}
    };
    $decide=static function($records,$qualified,$now)use($operation,$budget,$spec,$runtime,$public){
        $evidence=json_decode(privateFile($spec['evidence_file'],$public),true,64,JSON_THROW_ON_ERROR);
        return json_decode(\Mosa2\MarketCurrent\boundedPlanner([$runtime['python'],__DIR__.'/collector_scheduler_decision.py'],
            json_encode(['operation_config'=>$operation,'budget_config'=>$budget,'evidence'=>$evidence,'provider'=>$spec['provider'],
                'records'=>$records,'qualification'=>$qualified['qualification'],'now'=>iso(stamp($now))],JSON_THROW_ON_ERROR),$runtime,10),true,64,JSON_THROW_ON_ERROR);
    };
    $pipeline=static function($qualified,$cycle)use($root,$public,$password,$runtime,$spec){
        check(is_string($cycle)&&preg_match('/^cycle-[0-9]{8}t[0-9]{6}z$/D',$cycle)===1,'scheduler_cycle');
        $folder=$root.'/'.$cycle;check(!file_exists($folder)&&mkdir($folder,0700),'scheduler_cycle_exists');
        $entries=[];
        foreach($qualified['prepared'] as $i=>$entry){
            $item=$folder.'/asset-'.sprintf('%02d',$i+1);check(mkdir($item,0700),'scheduler_item');
            $f=fopen($item.'/live-manifest.json','x');check(is_resource($f),'scheduler_manifest');
            try{$wire=json_encode($entry['manifest'],JSON_THROW_ON_ERROR);same(fwrite($f,$wire),strlen($wire),'scheduler_manifest');check(fflush($f)&&fsync($f),'scheduler_manifest');}finally{fclose($f);}
            $entries[]=['private_root'=>$item];
        }
        return \Mosa2\MarketCurrent\run($folder,$password,$runtime,$entries,$spec['current_approvals']);
    };
    try{return tick($store,$operation,$budget,$qualify,$decide,$pipeline,$clock);}
    finally{unset($password);$p=null;}
}
if(PHP_SAPI==='cli'&&realpath($_SERVER['SCRIPT_FILENAME']??'')===__FILE__){
    ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
    try{$result=main($argv);}catch(Throwable){$result=['status'=>'BLOCKED','reason'=>'STOP_AND_REQUIRE_REVIEW'];}
    echo json_encode($result,JSON_THROW_ON_ERROR)."\n";
    exit(in_array($result['status'],['COMPLETE','SKIP'],true)?0:1);
}
