<?php
declare(strict_types=1);
namespace Mosa2\MarketCurrent;

/** Only fixed codes and monotonic durations cross the private process boundary. */
final class Outcome {
    public string $phase='PREFLIGHT', $commit='NOT_ATTEMPTED', $rollback='NOT_ATTEMPTED';
    public bool $transaction=false, $writeAttempted=false, $readback=false, $replay=false;
    public string $cause='NONE';
    private float $started, $phaseStarted;
    private array $durations=[];
    public function __construct(private mixed $emit=null) {$this->started=$this->phaseStarted=(hrtime(true)/1e9);}
    public function step(string $phase): void {
        $this->durations[$this->phase]=($this->durations[$this->phase]??0)+((hrtime(true)/1e9)-$this->phaseStarted);
        $this->phase=$phase;$this->phaseStarted=(hrtime(true)/1e9);
        if($this->emit!==null)($this->emit)(['kind'=>'progress']+$this->report());
    }
    public function budget(bool $beforeCommit=false): void {
        if((hrtime(true)/1e9)-$this->started>($beforeCommit?120:210)){
            $this->cause='PHASE_TIMEOUT';throw new \RuntimeException('current_phase_timeout');
        }
    }
    public function status(bool $success=false): string {
        if($this->commit==='UNKNOWN')return 'OUTCOME_UNKNOWN';
        if($this->commit==='CONFIRMED'){
            if($success&&$this->readback&&$this->replay)return 'CURRENT_COMMITTED_READBACK_AND_REPLAY_PASS';
            return $this->cause==='NONE'?'COMMIT_CONFIRMED_READBACK_PENDING':'ERROR_AFTER_COMMIT';
        }
        if($this->rollback==='CONFIRMED')return 'ROLLBACK_CONFIRMED';
        if($this->rollback==='UNKNOWN')return 'OUTCOME_UNKNOWN';
        return $this->transaction?'TRANSACTION_FAILED_BEFORE_COMMIT':'PREFLIGHT_FAILED_NO_WRITE';
    }
    public function report(bool $success=false): array {
        $times=$this->durations;$times[$this->phase]=($times[$this->phase]??0)+((hrtime(true)/1e9)-$this->phaseStarted);
        return ['status'=>$this->status($success),'phase'=>$this->phase,'commit'=>$this->commit,
            'rollback'=>$this->rollback,'transaction_started'=>$this->transaction,'write_attempted'=>$this->writeAttempted,
            'readback_confirmed'=>$this->readback,'replay_unchanged'=>$this->replay,'cause'=>$this->cause,
            'elapsed_ms'=>(int)round(((hrtime(true)/1e9)-$this->started)*1000),
            'phase_ms'=>array_map(static fn($v)=>(int)round($v*1000),$times)];
    }
}
