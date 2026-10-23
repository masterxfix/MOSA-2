<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/scripts/collector_scheduler.php';
use Mosa2\Scheduler\RunStore;
final class MemoryRuns implements RunStore {
    public array $rows=[];public bool $locked=false;public bool $busy=false;public bool $failClaim=false;public bool $failFinish=false;
    public function lock():bool {if($this->busy||$this->locked)return false;return $this->locked=true;}
    public function unlock():void {$this->locked=false;}
    public function history():array {foreach($this->rows as $r)if($r['status']!=='completed')throw new RuntimeException('unresolved');return $this->rows;}
    public function claim(string $slot,int $requests,string $started):string {
        $this->history();$this->rows[]=['status'=>'running','slot'=>$slot,'requests'=>$requests];
        if($this->failClaim)throw new RuntimeException('lost commit acknowledgement');
        return (string)count($this->rows);
    }
    public function finish(string $id,array $summary,string $finished,bool $success):void {
        if($this->failFinish)throw new RuntimeException('lost finish acknowledgement');
        $this->rows[(int)$id-1]=['status'=>$success?'completed':'failed','summary'=>$summary];
    }
}
$scenario=$argv[1];$store=new MemoryRuns();$calls=0;$reservations=[];
$now=new DateTimeImmutable('2026-10-21T10:00:07Z');
$operation=['execution_enabled'=>true];$budget=['execution_enabled'=>true];
$qualify=static fn()=>['prepared'=>[['manifest'=>[]]]];
$decision=static function($rows,$q,$t)use($scenario){
    if($scenario==='missing-calendar')return ['decision'=>'BLOCKED','reason'=>'CONFIGURATION_OR_CALENDAR_UNKNOWN'];
    if($rows!==[])return ['decision'=>'SKIP','reason'=>'SLOT_SKIPPED'];
    return ['decision'=>'RUN_ELIGIBLE','scheduled_at'=>'2026-10-21T10:00:00Z','cycle_id'=>'cycle-20261021t100000z'];
};
$pipeline=static function($q,$cycle)use(&$calls,$store,$scenario,&$reservations){
    $calls++;$reservations[]=$store->rows[0]['status'];
    if($scenario==='crash')throw new RuntimeException('SECRET must never reach output');
    if($scenario==='parallel'){
        $nested=\Mosa2\Scheduler\tick($store,['execution_enabled'=>true],['execution_enabled'=>true],
            static fn()=>throw new RuntimeException('parallel must not qualify'),
            static fn()=>[],static fn()=>throw new RuntimeException('parallel must not fetch'),
            static fn()=>new DateTimeImmutable('2026-10-21T10:00:07Z'));
        if($nested!==['status'=>'SKIP','reason'=>'BUSY'])throw new RuntimeException('parallel');
    }
    return ['ok'=>true,'overall_status'=>'COMPLETE','completed_count'=>1,
        'current'=>['committed'=>true,'readback'=>$scenario==='readback-failure'?'FAIL':'PASS']];
};
$clock=static fn()=>$now;
if($scenario==='disabled')$operation['execution_enabled']=false;
if($scenario==='busy')$store->busy=true;
if($scenario==='unknown')$store->rows=[['status'=>'running']];
if($scenario==='failed')$store->rows=[['status'=>'failed']];
if($scenario==='claim-unknown')$store->failClaim=true;
if($scenario==='finish-unknown')$store->failFinish=true;
if($scenario==='qualification-failure')$qualify=static fn()=>throw new RuntimeException('SECRET');
if($scenario==='missed-slot')$clock=static fn()=>new DateTimeImmutable('2026-10-21T10:01:00Z');
$first=\Mosa2\Scheduler\tick($store,$operation,$budget,$qualify,$decision,$pipeline,$clock);
$second=\Mosa2\Scheduler\tick($store,$operation,$budget,$qualify,$decision,$pipeline,$clock);
echo json_encode(['first'=>$first,'second'=>$second,'calls'=>$calls,'reservations'=>$reservations,'rows'=>$store->rows],JSON_THROW_ON_ERROR);
